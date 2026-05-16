# Rich Live CLI Runner demo tape
# Requires: vhs (https://github.com/charmbracelet/vhs)
#
# Usage:
#   vhs docs/assets/rich-live-demo.tape
#
# Prerequisites:
#   pip install -e ".[dev]"
#   mkdir -p /tmp/demo-project && cd /tmp/demo-project
#   miniautogen init demo --template quickstart
#   # Create a deliberation flow with 3 agents
#   miniautogen run main --input "Explain multi-agent orchestration"

Output: docs/assets/rich-live-demo.gif

# Terminal setup
Set FontSize 14
Set Width 120
Set Height 30
Set Theme "Catppuccin Mocha"

Type "miniautogen run main --input 'Explain multi-agent orchestration'" Sleep 500ms
Enter
Sleep 8s
Ctrl+C
Sleep 2s
