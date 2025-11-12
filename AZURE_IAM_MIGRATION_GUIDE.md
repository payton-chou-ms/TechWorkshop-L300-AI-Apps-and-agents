# Azure Storage IAM 遷移指南

## 📋 概述

程式碼已成功更新為使用 **Azure Identity (IAM/Managed Identity)** 取代共享金鑰來存取 Blob Storage。這是更安全且符合 Azure 最佳實踐的做法。

**您的儲存帳戶資訊：**
- Storage Account: `uzyslpn3y564qsa`
- Container: `zava`

---

## ✅ 已完成的程式碼變更

### 1. `src/app/tools/imageCreationTool.py`
```python
# ✅ 新增匯入
from azure.identity import DefaultAzureCredential

# ❌ 移除
blob_connection_string = os.getenv("blob_connection_string", "")

# ✅ 更新為使用 Managed Identity
account_url = f"https://{storage_account_name}.blob.core.windows.net"
credential = DefaultAzureCredential()
blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
```

### 2. `src/.env`
```env
# blob_connection_string 不再需要
# blob_connection_string=""
storage_account_name="uzyslpn3y564qsa"
storage_container_name="zava"
```

### 3. 相依套件
✅ `azure-identity==1.25.1` 已包含在 `requirements.txt` 中

---

## ⚠️ 必要操作：設定 Azure Portal IAM 權限

程式碼已準備好，但您**必須**在 Azure Portal 設定權限：

### 步驟 1：為您的使用者帳戶新增角色（本地開發用）

1. 前往 [Azure Portal](https://portal.azure.com/) → 搜尋 `uzyslpn3y564qsa`
2. 點選左側選單的 **Access Control (IAM)**
3. 點選 **+ Add** → **Add role assignment**
4. **Role** 頁籤：
   - 搜尋並選擇：**Storage Blob Data Contributor**
   - 點選 **Next**
5. **Members** 頁籤：
   - 選擇 **User, group, or service principal**
   - 點選 **+ Select members**
   - 搜尋您的 email
   - 選擇您的帳戶並點選 **Select**
6. 點選 **Review + assign** 兩次完成

### 步驟 2：為 App Service 新增角色（生產環境用）

1. 前往 Azure Portal → 搜尋 `uzyslpn3y564qsa`
2. 點選左側選單的 **Access Control (IAM)**
3. 點選 **+ Add** → **Add role assignment**
4. **Role** 頁籤：
   - 選擇：**Storage Blob Data Contributor**
   - 點選 **Next**
5. **Members** 頁籤：
   - 選擇 **Managed identity**
   - 點選 **+ Select members**
   - **Managed identity** 下拉選單：選擇 **App Service** 或 **Web App**
   - 找到並選擇您的 app service（例如：`uzyslpn3y564q-app`）
   - 點選 **Select**
6. 點選 **Review + assign** 兩次完成

### 步驟 3：確認 App Service 已啟用 Managed Identity

1. 前往 App Service → **Identity** → **System assigned**
2. 確認 Status 為 **On**

---

## 🧪 驗證步驟

### 本地測試
```bash
# 1. 登入 Azure CLI
az login

# 2. 驗證可以存取 storage
az storage blob list --account-name uzyslpn3y564qsa --container-name zava --auth-mode login

# 3. 執行應用程式
cd src
python chat_app.py
```

### 檢查角色指派
1. 前往 Storage Account → Access Control (IAM) → Role assignments
2. 篩選條件：**Storage Blob Data Contributor**
3. 應該可以看到您的使用者帳戶和/或 App Service

### 生產環境測試
1. 部署至 App Service
2. 透過應用程式嘗試上傳圖片
3. 檢查 App Service logs 是否有錯誤

---

## 🔍 常見問題排解

| 錯誤訊息 | 解決方案 |
|---------|---------|
| "This request is not authorized to perform this operation" | 等待 5-10 分鐘讓 IAM 角色生效 |
| "DefaultAzureCredential failed to retrieve a token" (本地) | 執行 `az login` 登入 |
| "DefaultAzureCredential failed to retrieve a token" (App Service) | 確認 Managed Identity 已啟用且角色已指派 |
| "The specified container does not exist" | 建立容器：`az storage container create --name zava --account-name uzyslpn3y564qsa --auth-mode login` |

