#!/usr/bin/env bash
#
# Skills 安装脚本 - 将当前仓库的 skills 链接到 ~/.agents/skills
#
# 用法:
#   ./install.sh                    # 使用脚本所在仓库
#   ./install.sh /path/to/repo      # 指定仓库路径
#   ./install.sh --mode=all         # 整个目录链接
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 输出函数
success() { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${CYAN}[..]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }
error() { echo -e "${RED}[XX]${NC} $1"; exit 1; }

# 解析参数
REPO_PATH=""
LINK_MODE="each"

while [[ $# -gt 0 ]]; do
    case $1 in
        --mode=all)
            LINK_MODE="all"
            shift
            ;;
        --mode=each)
            LINK_MODE="each"
            shift
            ;;
        -*)
            error "未知选项: $1"
            ;;
        *)
            REPO_PATH="$1"
            shift
            ;;
    esac
done

# 确定仓库路径
if [ -z "$REPO_PATH" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_PATH="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

# 验证仓库路径
SKILLS_PATH="$REPO_PATH/skills"
if [ ! -d "$SKILLS_PATH" ]; then
    error "Skills 目录不存在: $SKILLS_PATH"
fi

info "仓库路径: $REPO_PATH"
info "Skills 路径: $SKILLS_PATH"

# 创建主目录
AGENTS_SKILLS="$HOME/.agents/skills"
mkdir -p "$AGENTS_SKILLS"
success "创建目录: $AGENTS_SKILLS"

# 获取 skills 列表
SKILLS=($(ls -1 "$SKILLS_PATH"))
info "发现 ${#SKILLS[@]} 个 skills: ${SKILLS[*]}"

# 创建符号链接
if [ "$LINK_MODE" = "all" ]; then
    # 方式 A: 整个目录链接
    rm -rf "$AGENTS_SKILLS"
    ln -s "$SKILLS_PATH" "$AGENTS_SKILLS"
    success "链接整个目录: $AGENTS_SKILLS -> $SKILLS_PATH"
else
    # 方式 B: 单独链接每个 skill
    for skill in "${SKILLS[@]}"; do
        TARGET="$SKILLS_PATH/$skill"
        LINK="$AGENTS_SKILLS/$skill"

        # 删除已有链接
        [ -L "$LINK" ] && rm "$LINK"
        [ -d "$LINK" ] && rm -rf "$LINK"

        ln -s "$TARGET" "$LINK"
        success "链接: $skill"
    done
fi

# 检测 AI 工具并创建链接
TOOLS=("codebuddy" "trae-cn" "trae-aicc" "marscode" "lingma" "cursor" "windsurf")

info "检测 AI 工具目录..."

TOOLS_FOUND=0
for tool in "${TOOLS[@]}"; do
    TOOL_DIR="$HOME/.$tool"
    if [ -d "$TOOL_DIR" ]; then
        TOOLS_FOUND=$((TOOLS_FOUND + 1))
        SKILL_LINK="$TOOL_DIR/skills"

        # 删除已有链接
        [ -L "$SKILL_LINK" ] && rm "$SKILL_LINK"
        [ -d "$SKILL_LINK" ] && rm -rf "$SKILL_LINK"

        ln -s "$AGENTS_SKILLS" "$SKILL_LINK"
        success "链接到 $tool: $SKILL_LINK"
    fi
done

# 输出结果
echo ""
echo "========================================"
echo -e "${GREEN}安装完成!${NC}"
echo "========================================"
echo "Skills 主目录: $AGENTS_SKILLS"
echo "已安装 Skills: ${#SKILLS[@]} 个"
echo "已链接工具: $TOOLS_FOUND 个"
echo ""
echo -e "${YELLOW}验证安装:${NC}"
echo "  ls -la ~/.agents/skills/"
echo ""
echo -e "${YELLOW}更新 Skills:${NC}"
echo "  cd $REPO_PATH"
echo "  git pull"