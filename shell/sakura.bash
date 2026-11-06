# shellcheck shell=bash
# Source this from ~/.bashrc for Sakura's keys:
#   ?  open Sakura           ??  a coordinator with workers
#   ?remind tomorrow, 10am birthday wish
#   ?pa reply to all my emails saying I'm busy
if command -v sakura-launch >/dev/null 2>&1; then
    unalias '?' '??' '?pa' '?remind' 2>/dev/null
    alias '?'='sakura-launch'
    alias '??'='sakura-launch --coordinator'
    alias '?remind'='pa remind'
    alias '?pa'='pa ask'

    # What you type after these is a sentence, not shell. "I'm busy (idk)" would otherwise be a syntax error before anything
    # could run, so Enter quotes the sentence first. Only lines that start with one of these keys are touched.
    __sakura_quote_line() {
        local head rest
        case "$READLINE_LINE" in
            '?remind '*|'?pa '*|'? '*|'?? '*) ;;
            *) return 0 ;;
        esac
        head=${READLINE_LINE%% *}
        rest=${READLINE_LINE#* }
        case "$rest" in \'*\'|\"*\") return 0 ;; esac  # you already quoted it
        printf -v rest '%q' "$rest"
        READLINE_LINE="$head $rest"
        READLINE_POINT=${#READLINE_LINE}
    }
    if [[ $- == *i* ]] && [ -n "${BASH_VERSION:-}" ]; then
        bind -x '"\C-x\C-q": __sakura_quote_line' 2>/dev/null
        bind '"\C-m": "\C-x\C-q\C-j"' 2>/dev/null
        # Whatever came due while no notification could reach you.
        command -v pa >/dev/null 2>&1 && pa pending 2>/dev/null
    fi
fi
