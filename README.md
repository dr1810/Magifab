# Magifab
Every Story, for everyone

## Supabase Movie Storage

MagiFab now reads movie video URLs from Supabase Storage instead of local files in `public/movies`.

1. Copy `.env.example` to `.env.local`.
2. Fill in:
	- `VITE_SUPABASE_URL`
	- `VITE_SUPABASE_ANON_KEY`
	- `SUPABASE_SERVICE_ROLE_KEY` (local upload script only)
3. Ensure the Storage bucket `movies` is public.

### Upload Large Movie Files (TUS Resumable)

Use the local utility script with resumable uploads:

```bash
npm run upload:movies -- ./path/to/sprite-fright.webm ./path/to/big-buck-bunny.mov
```

The script uses the Supabase TUS endpoint:

- `POST {VITE_SUPABASE_URL}/storage/v1/upload/resumable`

and prints public URLs after successful upload.

Movie asset configuration is centralized in `src/config/movies.ts`.
