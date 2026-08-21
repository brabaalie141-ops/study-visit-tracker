# Study Visit Tracker V8.1

This package is generated from the working `app.py` supplied for the Study Visit Tracker.

## Important

V8.1 preserves the working application as the safe baseline. Before switching the live app to Supabase authentication and row-level permissions, verify that the Supabase tables and columns used by the project match the application schema.

### Streamlit secrets

When the Supabase-backed version is enabled, configure these in Streamlit Cloud Secrets:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY"
```

Never commit these secrets to GitHub.

## Deployment

1. Replace the repository's `app.py` with the supplied V8.1 `app.py`.
2. Keep `requirements.txt` in the repository.
3. Commit and push to GitHub.
4. Streamlit Cloud will redeploy.
5. Test with demo data first.
6. Only after permissions are verified should real participant data be introduced.

## Recommended V8.1 security test

- RA A can see only assigned participants.
- RA B cannot see RA A's participants.
- RO can review submitted visits.
- SRA can oversee the study and manage assignments.
- Every review/assignment change has an audit entry.

Do not enter real participant information until this test passes.
