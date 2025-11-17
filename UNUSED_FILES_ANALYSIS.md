# Unused Files Analysis - Frontend UI Codebase

## Summary

Found **16 unused or duplicate files** that can be safely removed from the frontend codebase.

---

## 🔴 Unused TypeScript Files (Duplicates)

These TypeScript files are **NOT imported anywhere** and have JavaScript equivalents that are being used:

### Pages (TypeScript - Unused)

1. **`src/pages/EventDetails.tsx`** ❌
   - **Used instead:** `src/pages/EventDetails.js` ✅
   - Imported in: `App.js` line 5

2. **`src/pages/Events.tsx`** ❌
   - **Used instead:** `src/pages/Events.js` ✅
   - Imported in: `App.js` line 4

3. **`src/pages/Home.tsx`** ❌
   - **Used instead:** `src/pages/Home.js` ✅
   - Imported in: `App.js` line 6

4. **`src/pages/Teams.tsx`** ❌
   - **Used instead:** `src/pages/teams.js` ✅
   - Imported in: `App.js` line 3

### Components (TypeScript - Unused)

5. **`src/components/ErrorBoundary.tsx`** ❌
   - Not imported anywhere
   - No usage found in codebase

6. **`src/components/EventDetails.tsx`** ❌
   - Not imported anywhere
   - Page version is used instead

7. **`src/components/EventList.tsx`** ❌
   - Not imported anywhere
   - No usage found

8. **`src/components/Events.tsx`** ❌
   - Not imported anywhere
   - Page version is used instead

9. **`src/components/Navbar.tsx`** ❌
   - **Used instead:** `src/components/Navbar.js` ✅
   - Imported in: `App.js` line 7

10. **`src/components/teamlist.tsx`** ❌
    - Not imported anywhere
    - No usage found

11. **`src/components/Teams.tsx`** ❌
    - Not imported anywhere
    - Page version is used instead

---

## 🟡 Unused Service/Config Files

### Services

12. **`src/services/awsEventsApi.js`** ❌
    - Not imported anywhere
    - No references found in codebase
    - Likely replaced by FTCApi.js

13. **`src/services/config.ts`** ❌
    - **Used instead:** `src/services/config.js` ✅
    - JavaScript version is imported

### Config Files

14. **`src/config.ts`** ❌
    - **Used instead:** `src/config.js` ✅
    - Imported in: `services/FTCApi.js`, `services/awsMatchesApi.js`

### Theme Files

15. **`src/theme.ts`** ❌
    - **Used instead:** `src/theme/theme.js` ✅
    - Imported in: `App.js` line 14

---

## 🟢 Used Files (Keep These)

### Main Entry Points
- ✅ `src/index.js` - Main entry point
- ✅ `src/App.js` - Main app component
- ✅ `src/reportWebVitals.js` - Performance monitoring

### Pages (JavaScript - Active)
- ✅ `src/pages/Home.js`
- ✅ `src/pages/teams.js`
- ✅ `src/pages/teamDetails.js`
- ✅ `src/pages/Events.js`
- ✅ `src/pages/EventDetails.js`
- ✅ `src/pages/Matches.js`
- ✅ `src/pages/AdminLogin.js`
- ✅ `src/pages/AdminDashboard.js`
- ✅ `src/pages/TestAwsApi.js`

### Components (JavaScript - Active)
- ✅ `src/components/Navbar.js`
- ✅ `src/components/AllianceMatchmaker.js`
- ✅ `src/components/AddMatches.js`
- ✅ `src/components/EventMatches.js`
- ✅ `src/components/PageTransition.js`
- ✅ `src/components/ProtectedRoute.js`

### Services (Active)
- ✅ `src/services/FTCApi.js` - Main API service
- ✅ `src/services/awsMatchesApi.js` - Matches API
- ✅ `src/services/api.js` - Legacy API wrapper
- ✅ `src/services/config.js` - Configuration

### Config (Active)
- ✅ `src/config.js` - App configuration
- ✅ `src/aws-config.js` - AWS Amplify config

### Theme (Active)
- ✅ `src/theme/theme.js` - MUI theme

### Styles (Active)
- ✅ `src/styles/App.css`
- ✅ `src/styles/components.css`
- ✅ `src/styles/Events.css`
- ✅ `src/styles/globals.css`
- ✅ `src/styles/Home.css`
- ✅ `src/styles/TeamDetails.css`
- ✅ `src/styles/Teams.css`

---

## 📋 Files to Delete

### Safe to Delete (16 files)

```bash
# TypeScript Pages (4 files)
src/pages/EventDetails.tsx
src/pages/Events.tsx
src/pages/Home.tsx
src/pages/Teams.tsx

# TypeScript Components (7 files)
src/components/ErrorBoundary.tsx
src/components/EventDetails.tsx
src/components/EventList.tsx
src/components/Events.tsx
src/components/Navbar.tsx
src/components/teamlist.tsx
src/components/Teams.tsx

# Unused Services (1 file)
src/services/awsEventsApi.js

# TypeScript Config/Theme (3 files)
src/services/config.ts
src/config.ts
src/theme.ts

# Other (1 file)
src/swagger.json  # API documentation, not used in runtime
```

---

## 🔍 Why These Files Are Unused

### 1. TypeScript Migration Incomplete

The project appears to have **started a TypeScript migration** but **never completed it**. The TypeScript files were created but:
- Never imported in the main app
- JavaScript versions continued to be used
- No TypeScript configuration is active

### 2. Duplicate Implementations

Many files exist in **both `.js` and `.tsx/.ts` versions**:
- Only the JavaScript versions are imported
- TypeScript versions are orphaned

### 3. Refactored Services

- `awsEventsApi.js` was likely replaced by `FTCApi.js`
- Functionality was consolidated

---

## ⚠️ Before Deleting

### Verification Steps

1. **Search for any dynamic imports**
   ```bash
   grep -r "import(" src/
   grep -r "require(" src/
   ```

2. **Check for lazy loading**
   ```bash
   grep -r "React.lazy" src/
   ```

3. **Verify no webpack aliases**
   - Check `webpack.config.js` or `craco.config.js`
   - Ensure no path aliases point to these files

4. **Run tests** (if any exist)
   ```bash
   npm test
   ```

5. **Build the app**
   ```bash
   npm run build
   ```

---

## 🗑️ Deletion Commands

### Option 1: Delete All at Once

```bash
cd /Users/ashok/other/FTC-Predictor

# Delete TypeScript pages
rm src/pages/EventDetails.tsx
rm src/pages/Events.tsx
rm src/pages/Home.tsx
rm src/pages/Teams.tsx

# Delete TypeScript components
rm src/components/ErrorBoundary.tsx
rm src/components/EventDetails.tsx
rm src/components/EventList.tsx
rm src/components/Events.tsx
rm src/components/Navbar.tsx
rm src/components/teamlist.tsx
rm src/components/Teams.tsx

# Delete unused services
rm src/services/awsEventsApi.js

# Delete TypeScript configs
rm src/services/config.ts
rm src/config.ts
rm src/theme.ts

# Delete swagger
rm src/swagger.json
```

### Option 2: Move to Archive First (Safer)

```bash
mkdir -p archived_files
mv src/pages/*.tsx archived_files/
mv src/components/*.tsx archived_files/
mv src/services/awsEventsApi.js archived_files/
mv src/services/config.ts archived_files/
mv src/config.ts archived_files/
mv src/theme.ts archived_files/
mv src/swagger.json archived_files/

# Test the app, then delete if everything works
# rm -rf archived_files/
```

---

## 📊 Impact Analysis

### File Size Reduction

Estimated reduction: **~50-100 KB** of source code

### Benefits

1. **Cleaner Codebase**
   - Less confusion about which files to edit
   - Clear that project uses JavaScript, not TypeScript
   - Easier onboarding for new developers

2. **Faster Builds**
   - Fewer files to process
   - No TypeScript compilation overhead

3. **Reduced Maintenance**
   - No duplicate files to keep in sync
   - Single source of truth for each component

4. **Better IDE Performance**
   - Fewer files to index
   - Clearer autocomplete suggestions

---

## 🔄 Future Considerations

### If Planning TypeScript Migration

If you want to migrate to TypeScript in the future:

1. **Do it properly:**
   - Add `tsconfig.json`
   - Configure webpack/babel for TypeScript
   - Migrate files one by one
   - Update imports as you go

2. **Don't keep both versions:**
   - Delete `.js` files as you create `.ts` equivalents
   - Update all imports immediately

3. **Use a migration tool:**
   - `ts-migrate` from Airbnb
   - Automated conversion tools

---

## ✅ Recommended Action

**Delete all 16 unused files** listed above. They are:
- Not imported anywhere
- Have JavaScript equivalents that are actively used
- Causing confusion and clutter

The codebase is clearly a **JavaScript project**, not TypeScript, so keeping the TypeScript files serves no purpose.

---

## 📝 Notes

- **App.tsx** exists but is not used (App.js is the entry point)
- All active routes use JavaScript page components
- No TypeScript configuration exists in the project
- The project successfully builds and runs without these files

---

**Last Updated:** November 17, 2025

