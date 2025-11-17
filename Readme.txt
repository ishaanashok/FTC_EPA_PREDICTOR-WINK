to start backend server


cd c:\Users\Ishaan\Desktop\FTC-Predictor\server
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

$env:PATH = "$env:PATH;c:\Users\Ishaan\Desktop\FTC-Predictor\server\venv\Scripts"

c:\Users\Ishaan\Desktop\FTC-Predictor\server\venv\Scripts\uvicorn main:app --reload

Git commands:
 git config --local credential.helper ""
 git config --global credential.helper cache
 git push
 > provide username and PAT (personal Access Token from .git-credentials file)
 > Run this from "Git bash" console
 

 Build and deploy to S3 public site:
 > export NODE_ENV=production GENERATE_SOURCEMAP=false && npm run build && aws s3 sync build/ s3://ftc-predictor-frontend-stage/ --delete