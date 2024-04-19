echo "SETUP SCRIPT"
echo "------------\n"

echo "Creating a storage directory at path below..."
echo "\t$(pwd)/badges\n"
mkdir badges
sleep 1   # wait

echo "Creating a virtual environment at path below..."
echo "\t$(pwd)/.venv\n"
python3 -m venv .venv --upgrade-deps
sleep 1   # wait

echo "Activating virtual environment..."
source .venv/bin/activate
echo ""
sleep 1   # wait

echo "Installing the following libraries:"
cat subfiles/requirements.txt
echo ""
python3 -m pip install -r subfiles/requirements.txt
echo ""
sleep 1   # wait

deactivate

echo "Set up complete."