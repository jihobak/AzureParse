# UTF-8 출력 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ----------------------------------------------------
# 스크립트 시작: 에러 발생 시 즉시 중단
# ----------------------------------------------------
$ErrorActionPreference = 'Stop'

# ----------------------------------------------------
# 1) 공통 변수 정의
# ----------------------------------------------------
$resourceGroup  = "joe-rg" 
$location       = "eastus"
$openaiName     = "joe-openai-0708"
$searchName     = "joe-ai-search"
$storageName    = "joestorage"
$containerName  = "pdf-data"
$formRecognizerName = "joe-di-test"       # Form Recognizer 리소스 이름
$openaiSku = "S0"
$searchSku = "Basic"
$formRecognizerSku = "S0"                        # Form Recognizer SKU

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
# Write-Host "OpenAI Service creating..."
# az cognitiveservices account create `
#   --name $openaiName `
#   --resource-group $resourceGroup `
#   --kind OpenAI `
#   --sku $openaiSku `
#   --location $location

# ----------------------------------------------------
# 4) Azure AI Search 생성
# ----------------------------------------------------
# Write-Host "Azure AI Search creating..."
# az search service create `
#   --name $searchName `
#   --resource-group $resourceGroup `
#   --sku $searchSku `
#   --partition-count 1 `
#   --replica-count 1 `
#   --location $location

# ----------------------------------------------------
# 5) Azure Storage Account 생성
# ----------------------------------------------------
# Write-Host "Azure Storage Account creating..."
# az storage account create `
#   --name $storageName `
#   --resource-group $resourceGroup `
#   --location $location `
#   --sku Standard_LRS

# ----------------------------------------------------
# 6) Blob Storage Container 생성
# ----------------------------------------------------
# Write-Host "Blob storage container creating in Azure Storage Account..."
# az storage container create `
#   --name $containerName `
#   --account-name $storageName

# ----------------------------------------------------
# soft-deleted 리소스 확인 및 purge (create 이전에 삽입)
# ----------------------------------------------------
# ---> bash
# echo "Checking for soft-deleted Cognitive Services account..."
# if az cognitiveservices account show-deleted \
#      --location "$LOCATION" \
#      --resource-group "$RESOURCE_GROUP" \
#      --name "$OPENAI_NAME" \
#      &> /dev/null; then
#   echo "❗ 소프트 삭제된 계정 '$OPENAI_NAME' 발견. Purge 진행..."
#   az cognitiveservices account purge \
#     --location "$LOCATION" \
#     --resource-group "$RESOURCE_GROUP" \
#     --name "$OPENAI_NAME"
#   echo "✅ Purge 완료."
# else
#   echo "소프트 삭제된 계정 없음. 계속 진행합니다."
# fi
# <--- bash
Write-Host "Checking for soft-deleted Cognitive Services account..."

# 1) soft-deleted 리소스 확인
$found = $false
try {
    # -o none 로 출력 억제, Out-Null 로 남는 데이터도 제거
    az cognitiveservices account show-deleted `
      --location $location `
      --resource-group $resourceGroup `
      --name $formRecognizerName `
      -o none | Out-Null

    $found = $true
}
catch {
    # 예외가 발생하면 soft-deleted 리소스 없음
    $found = $false
}

# 2) 존재 여부에 따라 purge 또는 패스
if ($found) {
    Write-Host "❗ 소프트 삭제된 계정 '$formRecognizerName' 발견. Purge 진행..."
    az cognitiveservices account purge `
      --location $location `
      --resource-group $resourceGroup `
      --name $formRecognizerName

    Write-Host "✅ Purge 완료."
}
else {
    Write-Host "소프트 삭제된 계정 없음. 계속 진행합니다."
}
# ----------------------------------------------------
# 7) Form Recognizer (Document Intelligence) 생성
# ----------------------------------------------------
Write-Host "Form Recognizer (Document Intelligence) creating..."
az cognitiveservices account create `
  --name $formRecognizerName `
  --resource-group $resourceGroup `
  --kind FormRecognizer `
  --sku $formRecognizerSku `
  --location $location `
  --custom-domain $formRecognizerName `
  --yes

  # 예시: 생성된 endpoint 정보 확인
Write-Host "Form Recognizer Endpoint:"
az cognitiveservices account show `
  --name $formRecognizerName `
  --resource-group $resourceGroup `
  --query "properties.endpoint"

# ----------------------------------------------------
# 7-1) Endpoint & Key 조회
# ----------------------------------------------------
Write-Host "Retrieving Form Recognizer endpoint and key..."
$di_endpoint = az cognitiveservices account show `
  --name $formRecognizerName `
  --resource-group $resourceGroup `
  --query "properties.endpoint" -o tsv

$di_key = az cognitiveservices account keys list `
  --name $formRecognizerName `
  --resource-group $resourceGroup `
  --query "key1" -o tsv

Write-Host "Form Recognizer endpoint: $di_endpoint"
Write-Host "Form Recognizer Key: $di_key"