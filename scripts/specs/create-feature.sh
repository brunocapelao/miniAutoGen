#!/usr/bin/env bash
set -euo pipefail

# create-feature.sh — Cria a estrutura de spec-driven development para uma nova feature
# Uso: ./scripts/specs/create-feature.sh <nome-da-feature>
# TODO(review): Add optional git branch creation (Business Logic reviewer, 2026-03-18, Medium)

SPECS_DIR=".specs"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# --- Validação ---
if [[ $# -lt 1 ]]; then
  echo "Uso: $0 <nome-da-feature>"
  echo "Exemplo: $0 engine-retry-policy"
  exit 1
fi

FEATURE_NAME="$1"
# Sanitizar: lowercase, hifens no lugar de espaços
FEATURE_SLUG=$(echo "$FEATURE_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

if [[ -z "$FEATURE_SLUG" ]]; then
  echo "Erro: nome de feature inválido."
  exit 1
fi

# --- Encontrar próximo número sequencial ---
NEXT_NUM=1
if ls -d "$SPECS_DIR"/[0-9][0-9][0-9]-* 2>/dev/null | head -1 > /dev/null 2>&1; then
  LAST_NUM=$(ls -d "$SPECS_DIR"/[0-9][0-9][0-9]-* 2>/dev/null | sort -t/ -k2 | tail -1 | sed 's|.*/\([0-9]\{3\}\)-.*|\1|' | sed 's/^0*//')
  NEXT_NUM=$((LAST_NUM + 1))
fi

PADDED_NUM=$(printf "%03d" "$NEXT_NUM")
SPEC_DIR_NAME="${PADDED_NUM}-${FEATURE_SLUG}"
SPEC_PATH="${SPECS_DIR}/${SPEC_DIR_NAME}"

# --- Criar directório e copiar templates ---
mkdir -p "$SPEC_PATH"

cp "$SPECS_DIR/template.md" "$SPEC_PATH/spec.md"
cp "$SPECS_DIR/plan-template.md" "$SPEC_PATH/plan.md"
cp "$SPECS_DIR/tasks-template.md" "$SPEC_PATH/tasks.md"

# Substituir placeholders nos ficheiros
TODAY=$(date +%Y-%m-%d)
DISPLAY_NAME=$(echo "$FEATURE_SLUG" | tr '-' ' ')

sed -i '' "s/\[Nome da Feature\]/${DISPLAY_NAME}/g" "$SPEC_PATH/spec.md" 2>/dev/null || \
  sed -i "s/\[Nome da Feature\]/${DISPLAY_NAME}/g" "$SPEC_PATH/spec.md"

sed -i '' "s/YYYY-MM-DD/${TODAY}/g" "$SPEC_PATH/spec.md" 2>/dev/null || \
  sed -i "s/YYYY-MM-DD/${TODAY}/g" "$SPEC_PATH/spec.md"

sed -i '' "s/| NNN/| ${PADDED_NUM}/g" "$SPEC_PATH/spec.md" 2>/dev/null || \
  sed -i "s/| NNN/| ${PADDED_NUM}/g" "$SPEC_PATH/spec.md"

sed -i '' "s/\[Nome da Feature\]/${DISPLAY_NAME}/g" "$SPEC_PATH/plan.md" 2>/dev/null || \
  sed -i "s/\[Nome da Feature\]/${DISPLAY_NAME}/g" "$SPEC_PATH/plan.md"

sed -i '' "s/YYYY-MM-DD/${TODAY}/g" "$SPEC_PATH/plan.md" 2>/dev/null || \
  sed -i "s/YYYY-MM-DD/${TODAY}/g" "$SPEC_PATH/plan.md"

sed -i '' "s/| NNN/| ${PADDED_NUM}/g" "$SPEC_PATH/plan.md" 2>/dev/null || \
  sed -i "s/| NNN/| ${PADDED_NUM}/g" "$SPEC_PATH/plan.md"

sed -i '' "s/\[Nome da Feature\]/${DISPLAY_NAME}/g" "$SPEC_PATH/tasks.md" 2>/dev/null || \
  sed -i "s/\[Nome da Feature\]/${DISPLAY_NAME}/g" "$SPEC_PATH/tasks.md"

sed -i '' "s/YYYY-MM-DD/${TODAY}/g" "$SPEC_PATH/tasks.md" 2>/dev/null || \
  sed -i "s/YYYY-MM-DD/${TODAY}/g" "$SPEC_PATH/tasks.md"

sed -i '' "s/| NNN/| ${PADDED_NUM}/g" "$SPEC_PATH/tasks.md" 2>/dev/null || \
  sed -i "s/| NNN/| ${PADDED_NUM}/g" "$SPEC_PATH/tasks.md"

# --- Criar branch ---
BRANCH_NAME="feat/${PADDED_NUM}-${FEATURE_SLUG}"

echo ""
echo "════════════════════════════════════════════════════"
echo "  Spec criada com sucesso!"
echo "════════════════════════════════════════════════════"
echo ""
echo "  Directório:  ${SPEC_PATH}/"
echo "  Ficheiros:"
echo "    - ${SPEC_PATH}/spec.md      (especificação)"
echo "    - ${SPEC_PATH}/plan.md      (plano técnico)"
echo "    - ${SPEC_PATH}/tasks.md     (decomposição de tarefas)"
echo ""
echo "  Branch sugerida: ${BRANCH_NAME}"
echo ""
echo "  Próximos passos:"
echo "    1. git checkout -b ${BRANCH_NAME}"
echo "    2. Preencha ${SPEC_PATH}/spec.md"
echo "    3. Use /spec-plan para gerar o plano técnico"
echo "    4. Use /spec-tasks para decompor em tarefas"
echo "    5. Comece a implementar (test-first!)"
echo ""
