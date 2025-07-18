# ----------------------------------------------------
# 스크립트 시작: 에러 발생 시 즉시 중단
# ----------------------------------------------------
$ErrorActionPreference = 'Stop'

# ----------------------------------------------------
# 1) 공통 변수 정의
# ----------------------------------------------------
$resourceGroup  = "joe-rg" 
$location       = "eastus"
$openaiName     = "joe-openai-0703"
$searchName     = "joe-ai-search-0701"
$storageName    = "joestorage01"
$containerName  = "pdf-data"
$openaiSku      = "S0"
$searchSku      = "Basic"

# ----------------------------------------------------
# custom-domain 변수 생성
#   - 'azure' + '-' + location + '-' + openaiName 형식으로 조합
# ----------------------------------------------------
$customDomain = "azure-$location-$openaiName"
# 결과 예시: "azure-eastus-joe-openai-0702"


# ----------------------------------------------------
# 2) Resource Group 생성
# ----------------------------------------------------
Write-Host "Resource Group creating..."
az group create `
  --name $resourceGroup `
  --location $location

# ----------------------------------------------------
# 3) OpenAI Service 생성
# ----------------------------------------------------
Write-Host "OpenAI Service creating..."
az cognitiveservices account create `
  --name $openaiName `
  --resource-group $resourceGroup `
  --kind OpenAI `
  --sku $openaiSku `
  --location $location `
  --custom-domain $customDomain

# az openai account create `
#     --name $openaiName `
#     --resource-group $resourceGroup `
#     --location $location `
#     --sku $openaiSku

# ----------------------------------------------------
# 4) Azure AI Search 생성
# ----------------------------------------------------
Write-Host "Azure AI Search creating..."
az search service create `
  --name $searchName `
  --resource-group $resourceGroup `
  --sku $searchSku `
  --partition-count 1 `
  --replica-count 1 `
  --location $location `
  --identity-type SystemAssigned

# Write-Host "Remove Managed Identity..."
# az search service update `
#   --name $searchName `
#   --resource-group $resourceGroup `
#   --identity-type None

# ----------------------------------------------------
# 5) Azure Storage Account 생성
# ----------------------------------------------------
Write-Host "Azure Storage Account creating..."
az storage account create `
  --name $storageName `
  --resource-group $resourceGroup `
  --location $location `
  --sku Standard_LRS `

# ----------------------------------------------------
# 6) Blob Storage Container 생성
# ----------------------------------------------------
Write-Host "Blob storage container creating in Azure Storage Account..."
az storage container create `
  --name $containerName `
  --account-name $storageName `

# ----------------------------------------------------
# 7) Search 서비스의 Principal ID 추출
# ----------------------------------------------------
$searchPrincipalId = az search service show `
  --name $searchName `
  --resource-group $resourceGroup `
  --query "identity.principalId" -o tsv

if ([string]::IsNullOrWhiteSpace($searchPrincipalId)) {
  Write-Error "❌ Search service에 Managed Identity가 설정되지 않았습니다. --identity-type SystemAssigned 옵션을 확인하세요."
  exit 1
}

# ----------------------------------------------------
# 8) Storage Blob Data Reader 역할 부여
# ----------------------------------------------------
$storageScope = az storage account show `
  --name $storageName `
  --resource-group $resourceGroup `
  --query "id" -o tsv

az role assignment create `
  --assignee $searchPrincipalId `
  --role "Storage Blob Data Reader" `
  --scope $storageScope

# ----------------------------------------------------
# 9) OpenAI 호출 권한 부여
# ----------------------------------------------------
$openaiScope = az cognitiveservices account show `
  --name $openaiName `
  --resource-group $resourceGroup `
  --query "id" -o tsv
if ([string]::IsNullOrWhiteSpace($openaiScope)) {
  Write-Error "❌ Cognitive Services 계정 '$openaiName' 을(를) 찾을 수 없습니다. 변수 값을 확인하세요."
  exit 1
}

az role assignment create `
  --assignee $searchPrincipalId `
  --role "Cognitive Services OpenAI User" `
  --scope $openaiScope

Write-Host "Finish"