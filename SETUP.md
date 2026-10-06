# Setup (about 10 minutes)

This is a complete, self-contained build. No template is needed.

1. Create a PUBLIC repo named exactly `LULULUNISAAC` (empty is fine).
2. Upload everything in this folder, keeping the structure:
   build.py, config.yml, requirements.txt, README.md, README.zh-TW.md,
   contact-button.html, and the `.github/workflows/build.yml` file.
   Tip: if `.github` is skipped by drag-and-drop, use Add file > Create new file,
   type `.github/workflows/build.yml` as the name and paste the contents.
3. Settings > Actions > General:
   - Allow all actions and reusable workflows
   - Workflow permissions: Read and write
4. Actions > build-profile > Run workflow. Wait for the green check.
5. Open github.com/LULULUNISAAC. (Image caching can take a few minutes.)

Edit text and numbers only in config.yml. Change the look in build.py (colours at the top).

Private contributions: create a classic personal access token with `read:user`,
save it as repo secret PROFILE_TOKEN.

Email: put contact-button.html on your website at /#contact (set your name part).

Preview without network:  pip install pyyaml && python build.py --offline
