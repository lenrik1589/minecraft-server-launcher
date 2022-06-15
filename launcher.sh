SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]:-$0}"; )" &> /dev/null && pwd 2> /dev/null; )";
filename="${0##*/}"
echo "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR"
if [[ $SCRIPT_DIR != "$PWD" ]]; then
	cd "$HOME" || exit
fi
python3 -m launcher "$@"
