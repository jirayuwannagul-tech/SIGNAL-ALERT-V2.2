# Deploy V2.2 แยก Project

## GitHub
```bash
git checkout -b v2.2
git add .
git commit -m "v2.2.21: WebSocket Rebound System"
git push origin v2.2
```

## Railway
1. New Project
2. Deploy from GitHub → เลือก repo
3. Settings → Branch: v2.2
4. Copy Environment Variables จาก V2.1
5. Deploy

## ผลลัพธ์
- GitHub: main (V2.1) + v2.2 (V2.2)
- Railway: 2 projects ทดสอบควบคู่
- LINE: Token เดียวกัน แต่แจ้ง v2.2
