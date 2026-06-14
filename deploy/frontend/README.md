# GharBuddy Frontend Deployment

## Deploy to Vercel (Recommended)

```bash
cd Frontend
npx vercel --prod
```

Or connect `yenode/GharBuddy` via the Vercel dashboard:
1. **Framework:** Vite
2. **Root Directory:** `Frontend`
3. **Build Command:** `npm run build`
4. **Output Directory:** `dist`
5. **Environment Variable:** `VITE_API_URL=https://gharbuddy-api.onrender.com`

The `vercel.json` in this folder handles API proxy rewrites so the frontend calls `/api/*` which Vercel forwards to the backend.

## Deploy to Netlify

```bash
cd Frontend
npx netlify deploy --prod --dir=dist
```

Or connect via Netlify dashboard using `netlify.toml` settings.

## CORS

The FastAPI backend already allows all origins (`allow_origins=["*"]`). No CORS changes needed for production deployment.

## Environment Variables

| Variable | Value |
|---|---|
| `VITE_API_URL` | Your backend URL (e.g. `https://gharbuddy-api.onrender.com`) |
