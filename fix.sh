#!/bin/bash
cat > Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data/logs storage
CMD ["python", "-m", "app.main"]
EOF

V=$(($(cat version.txt) + 1))
echo "$V" > version.txt

git add Dockerfile version.txt
git commit -m "fix: auto-fix v2.2.$V"
git push origin main

git checkout v2.2
git merge main -m "merge: auto-fix"
git push origin v2.2
git checkout main

echo "✅ Done! Check Railway in 2 minutes"
