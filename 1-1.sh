#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Resource configuration
resourceGroup="techworkshop-l300-ai-agents-1"
cosmosDbAccountName="uzyslpn3y564q-cosmosdb"
# This is the name of your Azure AI Search account. It will be something like xxxxxxxxxxxxx-search
aiSearchName="uzyslpn3y564q-search"
# This is the name of your Azure AI Foundry account. It will be something like xxxxxxxxxxxxx
# In the deployment script, the Type is Microsoft.CognitiveServices/accounts
aiFoundryName="aif-uzyslpn3y564q"
# This is the name of your Azure AI Foundry project. It will be something like proj-xxxxxxxxxx.
# Its Type in the deployment script is Microsoft.CognitiveServices/accounts/projects
aiProjectName="proj-uzyslpn3y564q"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Starting Azure Role Assignment Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Get current user principal ID
echo -e "${YELLOW}[Step 1/8]${NC} Getting current user principal ID..."
principalId=`az ad signed-in-user show --query id -o tsv`
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Principal ID: $principalId${NC}"
else
    echo -e "${RED}✗ Failed to get principal ID${NC}"
    exit 1
fi
echo ""

# Step 2: Enable system-assigned managed identity for AI Search
echo -e "${YELLOW}[Step 2/8]${NC} Enabling system-assigned managed identity for AI Search service..."
az search service update --resource-group $resourceGroup --name $aiSearchName --set identity.type=SystemAssigned
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Managed identity enabled for AI Search${NC}"
else
    echo -e "${RED}✗ Failed to enable managed identity${NC}"
    exit 1
fi
echo ""

# Step 3: Get AI Search managed identity ID
echo -e "${YELLOW}[Step 3/8]${NC} Getting AI Search managed identity ID..."
aiSearchManagedIdentityId=`az search service show --resource-group $resourceGroup --name "$aiSearchName" --query identity.principalId -o tsv`
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AI Search Managed Identity ID: $aiSearchManagedIdentityId${NC}"
else
    echo -e "${RED}✗ Failed to get managed identity ID${NC}"
    exit 1
fi
echo ""

# Step 4: Assign Cosmos DB Data Reader role to current user
echo -e "${YELLOW}[Step 4/8]${NC} Assigning Cosmos DB Data Reader role to current user..."
az cosmosdb sql role assignment create --account-name $cosmosDbAccountName --resource-group $resourceGroup --scope "/" --principal-id $principalId --role-definition-id "00000000-0000-0000-0000-000000000002"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Cosmos DB Data Reader role assigned to user${NC}"
else
    echo -e "${YELLOW}⚠ Role may already exist or failed to assign${NC}"
fi
echo ""

# Step 5: Assign Cosmos DB Account Reader Role to AI Search
echo -e "${YELLOW}[Step 5/8]${NC} Assigning Cosmos DB Account Reader Role to AI Search..."
az role assignment create --assignee $aiSearchManagedIdentityId --role "Cosmos DB Account Reader Role" --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$resourceGroup/providers/Microsoft.DocumentDB/databaseAccounts/$cosmosDbAccountName"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Cosmos DB Account Reader Role assigned${NC}"
else
    echo -e "${YELLOW}⚠ Role may already exist or failed to assign${NC}"
fi
echo ""

# Step 6: Assign Cosmos DB Data Contributor role to AI Search
echo -e "${YELLOW}[Step 6/8]${NC} Assigning Cosmos DB Data Contributor role to AI Search..."
az cosmosdb sql role assignment create --account-name $cosmosDbAccountName --resource-group $resourceGroup --scope "/" --principal-id $aiSearchManagedIdentityId --role-definition-id "00000000-0000-0000-0000-000000000001"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Cosmos DB Data Contributor role assigned${NC}"
else
    echo -e "${YELLOW}⚠ Role may already exist or failed to assign${NC}"
fi
echo ""

# Step 7: Assign Cosmos DB Data Reader role to AI Search
echo -e "${YELLOW}[Step 7/8]${NC} Assigning Cosmos DB Data Reader role to AI Search..."
az cosmosdb sql role assignment create --account-name $cosmosDbAccountName --resource-group $resourceGroup --scope "/" --principal-id $aiSearchManagedIdentityId --role-definition-id "00000000-0000-0000-0000-000000000002"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Cosmos DB Data Reader role assigned${NC}"
else
    echo -e "${YELLOW}⚠ Role may already exist or failed to assign${NC}"
fi
echo ""

# Step 8: Assign Cognitive Services roles to AI Search
echo -e "${YELLOW}[Step 8/8]${NC} Assigning Cognitive Services roles to AI Search..."

echo -e "  ${BLUE}→${NC} Assigning 'Cognitive Services OpenAI User' to AI Project..."
az role assignment create --assignee $aiSearchManagedIdentityId --role "Cognitive Services OpenAI User" --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$resourceGroup/providers/Microsoft.CognitiveServices/accounts/$aiFoundryName/projects/$aiProjectName"
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓ Role assigned to AI Project${NC}"
else
    echo -e "  ${YELLOW}⚠ Role may already exist or failed to assign${NC}"
fi

echo -e "  ${BLUE}→${NC} Assigning 'Cognitive Services OpenAI User' to AI Foundry..."
az role assignment create --assignee $aiSearchManagedIdentityId --role "Cognitive Services OpenAI User" --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$resourceGroup/providers/Microsoft.CognitiveServices/accounts/$aiFoundryName"
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓ Role assigned to AI Foundry${NC}"
else
    echo -e "  ${YELLOW}⚠ Role may already exist or failed to assign${NC}"
fi

echo -e "  ${BLUE}→${NC} Assigning 'Cognitive Services Contributor' to AI Project..."
az role assignment create --assignee $aiSearchManagedIdentityId --role "Cognitive Services Contributor" --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$resourceGroup/providers/Microsoft.CognitiveServices/accounts/$aiFoundryName/projects/$aiProjectName"
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓ Role assigned${NC}"
else
    echo -e "  ${YELLOW}⚠ Role may already exist or failed to assign${NC}"
fi
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Role assignment setup completed!${NC}"
echo -e "${BLUE}========================================${NC}"
