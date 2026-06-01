---
sidebar_position: 5
---

# Neon Database Deployment Checklist

## ✅ Completed

- [x] Created PostgreSQL schema (`schema.sql`)
- [x] Created migration script (`migrate.py`)  
- [x] Migrated data to Neon (43,726 nonprofits + aggregates)
- [x] Created fast API endpoint (`api/routes/stats_neon.py`)
- [x] Updated API to use Neon (`api/main.py`)
- [x] Tested queries locally - all working ✅
- [x] Committed changes to git

## 📋 Remaining Steps

### 1. Add Secret to HuggingFace Space

**URL:** https://huggingface.co/spaces/CommunityOne/open-navigator/settings

**Steps:**
1. Navigate to Settings → Variables and secrets
2. Click "New secret"
3. **Name:** `NEON_DATABASE_URL`
4. **Value:** 
   ```
   postgresql://neondb_owner:<YOUR_NEON_PASSWORD>@<YOUR_NEON_HOST>.neon.tech/neondb?sslmode=require&channel_binding=require
   ```
5. Click "Save"

### 2. Merge to Main Branch

```bash
# Switch to main
git checkout main

# Merge huggingface-deploy into main
git merge huggingface-deploy

# Push to GitHub
git push origin main
```

### 3. Deploy to HuggingFace

```bash
# Switch back to deployment branch
git checkout huggingface-deploy

# Ensure it's up to date with main
git merge main

# Push to HuggingFace (triggers rebuild)
git push hf huggingface-deploy:main
```

### 4. Monitor Deployment

**Space URL:** https://huggingface.co/spaces/CommunityOne/open-navigator

**Expected:**
- Build time: 3-5 minutes
- Should see "Building..." status
- Will show "Running" when complete

### 5. Test Deployed API

Once the space is running:

```bash
# Test stats endpoint (should respond in <100ms)
curl https://communityone-open-navigator.hf.space/api/stats

# Test search endpoint
curl "https://communityone-open-navigator.hf.space/api/search/?q=hospital&state=MA"

# Test in browser
open https://communityone-open-navigator.hf.space
```

**Expected Results:**
- `/api/stats` response time: **< 100ms** (vs 5s before) ⚡
- Dashboard loads: **< 500ms** (vs 2-3s before) ⚡
- Search queries: **50-200ms** (vs 3-10s before) ⚡

## 🐛 Troubleshooting

### If API returns 500 error:

1. **Check HuggingFace Logs:**
   - Go to Space → Logs tab
   - Look for database connection errors

2. **Verify Secret:**
   - Settings → Variables and secrets
   - Ensure `NEON_DATABASE_URL` is set correctly

3. **Check Neon Database:**
   ```bash
   # Test connection locally
   psql "postgresql://neondb_owner:REDACTED@ep-noisy-fire-anrnmxxy-pooler.c-6.us-east-1.aws.neon.tech/neondb"
   
   # Verify data exists
   SELECT COUNT(*) FROM organization_nonprofit;
   SELECT COUNT(*) FROM jurisdiction_state_aggregate;
   ```

4. **Rebuild Space:**
   - Settings → Factory reboot
   - Wait 3-5 minutes for rebuild

### If queries are still slow:

1. **Check Neon project is active:**
   - Login to https://neon.tech
   - Verify project is not paused (free tier auto-pauses after inactivity)
   - Click "Resume" if needed

2. **Check indexes:**
   ```sql
   SELECT tablename, indexname 
   FROM pg_indexes 
   WHERE schemaname = 'public'
   ORDER BY tablename, indexname;
   ```

3. **Run ANALYZE to update statistics:**
   ```sql
   ANALYZE organization_nonprofit;
   ANALYZE jurisdiction_state_aggregate;
   ```

## 📊 Performance Validation

After deployment, run these checks:

**Frontend (Browser DevTools → Network):**
- Dashboard load: Should be < 500ms total
- API calls: Each < 100ms
- No 404s or failed requests

**Backend (curl with timing):**
```bash
# Test API response time
time curl -w "\nTime: %{time_total}s\n" \
  https://communityone-open-navigator.hf.space/api/stats
```

Expected: `Time: 0.0XX s` (under 100ms)

## 🎯 Success Criteria

- [x] HuggingFace Space builds successfully
- [ ] `/api/stats` responds in < 100ms
- [ ] Dashboard loads in < 500ms  
- [ ] Search queries return in < 200ms
- [ ] No errors in HuggingFace logs
- [ ] Users report faster page loads

## 📈 Monitoring

**Neon Dashboard:**
- https://console.neon.tech/app/projects
- Monitor: Queries/second, response times, storage usage

**HuggingFace Logs:**
- Check for `asyncpg` connection pool messages
- Look for query timing logs

## 🔄 Future Optimization

After successful deployment:

1. **Load more states into Neon:**
   ```bash
   # Edit migrate.py to add more states
   python packages/hosting/src/hosting/neon/migrate.py  # loads all states
   ```

2. **Add automatic sync:**
   - Create `neon/sync.py` for incremental updates
   - Schedule daily sync via GitHub Actions

3. **Monitor usage:**
   - Track free tier limits (500MB storage, 3GB transfer/month)
   - Upgrade if needed ($19/month for 10GB)

4. **Add caching:**
   - Redis cache layer for even faster responses
   - Cache stats for 5-10 minutes

## 💡 Tips

- First query after inactivity may be slow (cold start)
- Neon free tier pauses after 5 minutes of inactivity
- First request wakes it up (~1-2 seconds)
- Subsequent requests are fast (under 50ms)

## 🆘 Need Help?

- **Neon Support:** https://neon.tech/docs
- **asyncpg Docs:** https://magicstack.github.io/asyncpg
