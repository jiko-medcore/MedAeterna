"""Two-session SPEC-02 final-system-admin guard test for a local database."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import psycopg2
import pytest


DATABASE_URL = os.getenv("SPEC02_TEST_DATABASE_URL")


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="set SPEC02_TEST_DATABASE_URL to a dedicated local Supabase database",
)
def test_concurrent_final_system_admin_revocations_are_serialized():
    parsed = urlparse(DATABASE_URL)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("SPEC-02 concurrency tests are restricted to a local database")

    role_id = str(uuid.uuid4())
    user_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    emails = [f"spec02-race-{user_id}@example.test" for user_id in user_ids]
    barrier = threading.Barrier(2)
    created_role = False
    setup = psycopg2.connect(DATABASE_URL)
    try:
        with setup.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM public.user_roles ur
                JOIN public.roles r ON r.id = ur.role_id
                WHERE ur.status = 'active'
                  AND ur.organization_id IS NULL
                  AND r.name = 'super_admin'
                  AND r.role_type = 'system'
                  AND r.is_active IS TRUE
                """
            )
            if cursor.fetchone()[0]:
                pytest.skip("the dedicated test database already has an active system admin")

            cursor.execute(
                """
                INSERT INTO auth.users
                    (id, aud, role, email, raw_app_meta_data, raw_user_meta_data)
                VALUES
                    (%s, 'authenticated', 'authenticated', %s,
                     '{"provider":"email","providers":["email"]}', '{}'),
                    (%s, 'authenticated', 'authenticated', %s,
                     '{"provider":"email","providers":["email"]}', '{}')
                """,
                (user_ids[0], emails[0], user_ids[1], emails[1]),
            )
            cursor.execute(
                """
                SELECT id
                FROM public.roles
                WHERE name = 'super_admin'
                  AND role_type = 'system'
                  AND organization_id IS NULL
                  AND is_active IS TRUE
                LIMIT 1
                """
            )
            role_row = cursor.fetchone()
            if role_row:
                role_id = str(role_row[0])
            else:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM public.roles
                        WHERE name = 'super_admin'
                          AND role_type = 'system'
                          AND organization_id IS NULL
                    )
                    """
                )
                if cursor.fetchone()[0]:
                    pytest.skip("the system-admin role is present but inactive")
                cursor.execute(
                    """
                    INSERT INTO public.roles (id, name, role_type, organization_id, is_active)
                    VALUES (%s, 'super_admin', 'system', NULL, true)
                    """,
                    (role_id,),
                )
                created_role = True
            cursor.execute(
                """
                INSERT INTO public.user_roles (user_id, role_id, organization_id, status)
                VALUES (%s, %s, NULL, 'active'), (%s, %s, NULL, 'active')
                """,
                (user_ids[0], role_id, user_ids[1], role_id),
            )
        setup.commit()
    except Exception:
        setup.rollback()
        raise
    finally:
        setup.close()

    def revoke(target_user_id: str, actor_id: str):
        connection = psycopg2.connect(DATABASE_URL)
        try:
            connection.set_session(isolation_level="READ COMMITTED")
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL request.jwt.claim.role = 'service_role'")
                barrier.wait(timeout=10)
                try:
                    cursor.execute(
                        """
                        SELECT public.change_user_role_assignment(
                            %s, %s, NULL, %s, 'user', 'revoke',
                            'SPEC-02 two-session concurrency test'
                        )
                        """,
                        (target_user_id, role_id, actor_id),
                    )
                    result = cursor.fetchone()[0]
                    connection.commit()
                    return ("success", result["status"])
                except psycopg2.Error as error:
                    outcome = ("error", error.pgcode, error.diag.message_primary)
                    connection.rollback()
                    return outcome
        finally:
            connection.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            pending = [
                executor.submit(revoke, user_ids[0], user_ids[1]),
                executor.submit(revoke, user_ids[1], user_ids[0]),
            ]
            outcomes = [future.result(timeout=20) for future in pending]

        assert sum(outcome[0] == "success" for outcome in outcomes) == 1
        assert sum(len(outcome) > 1 and outcome[1] == "23514" for outcome in outcomes) == 1

        verify = psycopg2.connect(DATABASE_URL)
        try:
            with verify.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM public.user_roles
                    WHERE role_id = %s
                      AND user_id = ANY(%s::uuid[])
                      AND status = 'active'
                    """,
                    (role_id, user_ids),
                )
                assert cursor.fetchone()[0] == 1
        finally:
            verify.close()
    finally:
        cleanup = psycopg2.connect(DATABASE_URL)
        try:
            with cleanup.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.role_assignment_audit WHERE user_id = ANY(%s::uuid[])",
                    (user_ids,),
                )
                cursor.execute(
                    "DELETE FROM public.user_roles WHERE user_id = ANY(%s::uuid[])",
                    (user_ids,),
                )
                if created_role:
                    cursor.execute("DELETE FROM public.roles WHERE id = %s", (role_id,))
                cursor.execute("DELETE FROM auth.users WHERE id = ANY(%s::uuid[])", (user_ids,))
                cursor.execute(
                    "SELECT count(*) FROM auth.users WHERE email LIKE 'spec02-race-%@example.test'"
                )
                assert cursor.fetchone()[0] == 0
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cleanup.close()
