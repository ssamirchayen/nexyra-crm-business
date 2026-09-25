SELECT json_build_object(
    'database', current_database(),
    'server_version_num', current_setting('server_version_num')::integer,
    'revisions', (SELECT json_agg(version_num ORDER BY version_num) FROM public.alembic_version),
    'counts', json_build_object(
        'workspaces', (SELECT count(*) FROM public.workspaces),
        'users', (SELECT count(*) FROM public.users),
        'workspace_memberships', (SELECT count(*) FROM public.workspace_memberships),
        'user_credentials', (SELECT count(*) FROM public.user_credentials),
        'leads', (SELECT count(*) FROM public.leads),
        'opportunities', (SELECT count(*) FROM public.opportunities),
        'activities', (SELECT count(*) FROM public.activities),
        'audit_events', (SELECT count(*) FROM public.audit_events)
    ),
    'orphan_memberships', (
        SELECT count(*) FROM public.workspace_memberships AS m
        LEFT JOIN public.users AS u ON u.id = m.user_id
        LEFT JOIN public.workspaces AS w ON w.id = m.workspace_id
        WHERE u.id IS NULL OR w.id IS NULL
    )
);
