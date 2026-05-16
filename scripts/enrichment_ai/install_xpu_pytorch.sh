#!/bin/bash
set -e

echo "======================================================================"
echo "Installing PyTorch with Intel XPU Support"
echo "======================================================================"
echo ""

# Check if we're in the right venv
if [[ "$VIRTUAL_ENV" != *".venv-intel"* ]]; then
    echo "❌ Please activate .venv-intel first:"
    echo "   source .venv-intel/bin/activate"
    exit 1
fi

echo "📦 Current environment: $VIRTUAL_ENV"
echo ""

# Uninstall current PyTorch
echo "🗑️  Removing current PyTorch installation..."
pip uninstall -y torch torchvision torchaudio intel-extension-for-pytorch

# Install Intel PyTorch with XPU support
echo "📦 Installing PyTorch 2.5.0 with Intel XPU support..."
pip install torch==2.5.0a0 torchvision==0.20.0a0 torchaudio==2.5.0a0 \
    intel-extension-for-pytorch==2.5.0 \
    --extra-index-url https://pytorch-extension.intel.com/release-whl/stable/xpu/us/

echo ""
echo "======================================================================"
echo "✅ PyTorch with XPU Support Installed!"
echo "======================================================================"
echo ""

# Verify installation
echo "🔍 Verifying installation..."
python3 -c "
import torch
import intel_extension_for_pytorch as ipex

print('PyTorch version:', torch.__version__)
print('IPEX version:', ipex.__version__)
print('XPU available:', torch.xpu.is_available())

if torch.xpu.is_available():
    print('XPU device count:', torch.xpu.device_count())
    for i in range(torch.xpu.device_count()):
        print(f'  Device {i}:', torch.xpu.get_device_name(i))
else:
    print('⚠️  No XPU devices detected')
    print('   Make sure Intel GPU drivers are installed:')
    print('   sudo ./scripts/enrichment_ai/setup_intel_gpu.sh')
"

echo ""
echo "======================================================================"
echo "🎯 Next Steps:"
echo "======================================================================"
echo ""
echo "Test with bill analysis:"
echo "  cd /home/developer/projects/open-navigator"
echo "  source .venv-intel/bin/activate"
echo "  export HF_TOKEN=your_token"
echo "  python scripts/enrichment_ai/batch_analyze_bills.py --state AL --topic fluoride --limit 2"
echo ""
