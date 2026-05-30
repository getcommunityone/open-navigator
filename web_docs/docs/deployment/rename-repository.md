---
sidebar_position: 12
---

# Rename Repository & Make Public

This guide walks you through renaming your GitHub repository to "open-navigator-for-engagement" and making it public.

## 📋 Pre-Flight Checklist

Before you begin:
- [ ] Commit and push all local changes
- [ ] Backup your repository (optional but recommended)
- [ ] Ensure you have admin access to the repository
- [ ] Review what will be made public

## 🔄 Step 1: Rename Repository on GitHub

### Option A: Via GitHub Web Interface (Recommended)

1. **Navigate to your repository** on GitHub
2. **Click "Settings"** tab (top right)
3. **Scroll to "Repository name"** section
4. **Change name to:** `open-navigator-for-engagement`
5. **Click "Rename"** button

**✅ GitHub automatically:**
- Redirects old URL to new URL
- Updates all clone URLs
- Preserves issues, PRs, stars, watchers

### Option B: Via GitHub CLI

```bash
# Install GitHub CLI if not already installed
# sudo apt install gh  # Linux
# brew install gh      # macOS

# Authenticate
gh auth login

# Rename repository
gh repo rename open-navigator-for-engagement
```

## 🌍 Step 2: Make Repository Public

### Option A: Via GitHub Web Interface

1. **Still in Settings**, scroll down to **"Danger Zone"**
2. **Click "Change visibility"**
3. **Select "Make public"**
4. **Read the warnings** (sensitive data will be publicly visible)
5. **Type repository name to confirm:** `open-navigator-for-engagement`
6. **Click "I understand, change repository visibility"**

### Option B: Via GitHub CLI

```bash
gh repo edit --visibility public
```

## ⚠️ Important: Review Before Making Public

**Things that will become public:**
- ✅ All code and commit history
- ✅ All issues and pull requests
- ✅ All releases and tags
- ✅ Wiki pages
- ✅ GitHub Actions workflows

**Check for sensitive data:**
```bash
# Search for potential secrets
cd /home/developer/projects/open-navigator

# Check .env files (should be in .gitignore)
git ls-files | grep -E '\.env$'

# Check for API keys in committed files
git grep -i "api[_-]key"
git grep -i "secret"
git grep -i "password"
git grep -i "token"

# Review .gitignore
cat .gitignore
```

**Recommended .gitignore additions:**
```
# Secrets and credentials
.env
.env.local
*.pem
*.key
secrets/

# API tokens
*_token.txt
credentials.json

# Local configuration
config/local.py
```

## 🔗 Step 3: Update Local Repository

After renaming on GitHub:

```bash
cd /home/developer/projects/open-navigator

# Check current remote
git remote -v

# Update remote URL (replace USERNAME with your GitHub username/org)
git remote set-url origin https://github.com/getcommunityone/open-navigator-for-engagement.git

# Verify
git remote -v

# Fetch to confirm connection
git fetch

# Output should show:
# origin  https://github.com/getcommunityone/open-navigator-for-engagement.git (fetch)
# origin  https://github.com/getcommunityone/open-navigator-for-engagement.git (push)
```

## 📝 Step 4: Update Code References

Run the provided script to update all repository URLs in your code:

```bash
cd /home/developer/projects/open-navigator

# Make script executable
chmod +x update-repo-urls.sh

# Run the update script
./update-repo-urls.sh

# Review changes
git diff

# Commit the changes
git add .
git commit -m "chore: update repository name to open-navigator-for-engagement"
git push
```

### Manual Updates (if needed)

Key files to check:

1. **README.md** - Clone instructions
2. **setup.py** - Package metadata URLs
3. **website/docusaurus.config.ts** - Documentation links
4. **agents/scraper.py** - User-Agent string
5. **package.json** (if exists) - Repository field

## 🎯 Step 5: Update External Services (If Applicable)

If you're using external services, update them:

- **Databricks Apps**: Update app configuration
- **CI/CD Pipelines**: Update repository URLs
- **Webhooks**: Will automatically redirect
- **Badges**: Update markdown badge URLs
- **Documentation links**: Already handled by script

## ✅ Verification Checklist

After completing all steps:

- [ ] Repository renamed on GitHub
- [ ] Repository is now public
- [ ] Local git remote updated
- [ ] Code references updated
- [ ] Changes committed and pushed
- [ ] Old URL redirects to new URL
- [ ] Clone new repository works: `git clone https://github.com/getcommunityone/open-navigator-for-engagement.git`
- [ ] Documentation links work
- [ ] No sensitive data exposed

## 🔍 Test the New Repository

```bash
# Clone from new URL (in a different directory)
cd /tmp
git clone https://github.com/getcommunityone/open-navigator-for-engagement.git
cd open-navigator-for-engagement

# Verify it works
ls -la
cat README.md

# Clean up test
cd ..
rm -rf open-navigator-for-engagement
```

## 🎉 Post-Rename Actions

### Update Social & Marketing

- [ ] Update website links
- [ ] Update social media profiles
- [ ] Update blog posts or articles
- [ ] Update documentation sites
- [ ] Notify collaborators

### Add Repository Metadata

Make your repository discoverable:

1. **Add Topics** (on GitHub):
   - civic-tech
   - open-data
   - government-transparency
   - advocacy
   - policy-analysis
   - municipal-data
   - nonprofit-data

2. **Add Description**: "AI-powered platform analyzing municipal meetings and budgets across 90,000+ U.S. jurisdictions to identify advocacy opportunities"

3. **Add Website**: Link to your deployment or documentation

4. **Enable Discussions** (optional): Settings → Features → Discussions

5. **Add License Badge** to README (already has MIT badge)

## 📚 Documentation Updates

The script automatically updates:
- All README files
- Docusaurus configuration
- Python setup files
- Documentation pages
- Issue templates

## 🔒 Security Considerations

**After making public:**

1. **Enable Security Features**:
   - Go to Settings → Security
   - Enable Dependabot alerts
   - Enable Dependabot security updates
   - Enable Code scanning (if applicable)

2. **Add SECURITY.md**:
   ```markdown
   # Security Policy
   
   ## Reporting a Vulnerability
   
   Please report security vulnerabilities to: security@communityone.com
   ```

3. **Review Branch Protection**:
   - Protect main branch
   - Require pull request reviews
   - Require status checks

## 🆘 Troubleshooting

### Issue: "Repository not found" after rename

**Solution**: Update your local remote:
```bash
git remote set-url origin https://github.com/getcommunityone/open-navigator-for-engagement.git
```

### Issue: Old repository URL still accessible

**Expected**: GitHub automatically redirects old URLs to new ones for convenience.

### Issue: Collaborators can't access

**Solution**: They need to update their remotes too (same command as above).

### Issue: Sensitive data was committed

**Solutions**:
1. **Remove from history**: Use `git filter-repo` or BFG Repo-Cleaner
2. **Rotate secrets**: Change any exposed API keys, tokens, passwords
3. **Contact GitHub Support**: For complete removal assistance

## 📞 Support

- **GitHub Renaming Docs**: https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository
- **Making Public**: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility

## ✨ Success!

Your repository is now:
- ✅ Renamed to `open-navigator-for-engagement`
- ✅ Publicly accessible
- ✅ All references updated
- ✅ Ready for community contributions

**New Repository URL**: https://github.com/getcommunityone/open-navigator-for-engagement

Welcome to open source! 🎉
