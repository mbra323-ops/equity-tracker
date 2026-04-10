# EquiTrack — Claude Instructions

## Git workflow
After every commit, always run `git push` immediately.
Vercel is connected to the GitHub repo and deploys automatically on push — do NOT run `vercel --prod` manually.

The full commit workflow is:
```
git add <files>
git commit -m "message"
git push
```
