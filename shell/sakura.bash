# shellcheck shell=bash
# Source this from ~/.bashrc for Sakura's keys:
#   ?  open Sakura           ??  a coordinator with workers
#   ?remind tomorrow, 10am birthday wish
#   ?pa reply to all my emails saying I'm busy
#   ?fix  fix the command that just failed (words after it are a hint)
if command -v sakura-launch >/dev/null 2>&1; then
    unalias '?' '??' '?pa' '?remind' '?fix' 2>/dev/null
    alias '?'='sakura-launch'
    alias '?fix'='sakura-fix --shell $$'
    alias '??'='sakura-launch --coordinator'
    alias '?remind'='pa remind'
    alias '?pa'='pa ask'

    # What you type after these is a sentence, not shell. "I'm busy (idk)" would otherwise be a syntax error before anything
    # could run, so Enter quotes the sentence first. Only lines that start with one of these keys are touched.
    __sakura_quote_line() {
        local head rest
        case "$READLINE_LINE" in
            '?remind '*|'?pa '*|'?fix '*|'? '*|'?? '*) ;;
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

        # ?fix: remember the last command that failed, where, and how, so `?fix` needs no copying or explaining.
        # Ctrl-C (130) isn't a failure. Inside tmux the screen is kept too; otherwise ?fix reruns it when that's harmless.
        __sakura_preexec() { __sakura_cmd=$1; }
        __sakura_precmd() {
            local rc=$? dir="${XDG_RUNTIME_DIR:-/tmp}/sakura-fix-$UID" cmd
            if [ -n "${__bp_imported:-}" ]; then cmd=${__sakura_cmd:-}; __sakura_cmd=; else
                cmd=$(HISTTIMEFORMAT='' history 1); cmd=${cmd#*[0-9]  }; fi
            case "$rc:$cmd" in 0:*|130:*|*:|*:'?'*) return "$rc" ;; esac
            (umask 077; mkdir -p "$dir" && printf '%s\n%s\n%s\n%s\n' "$rc" "$(date +%s)" "$PWD" "$cmd" > "$dir/$$"
             if [ -n "${TMUX:-}" ]; then tmux capture-pane -p -S -120 > "$dir/$$.screen" 2>/dev/null; else rm -f "$dir/$$.screen"; fi)
            return "$rc"
        }
        if [ -n "${__bp_imported:-}" ]; then
            preexec_functions+=(__sakura_preexec); precmd_functions+=(__sakura_precmd)
        else
            case ";${PROMPT_COMMAND:-};" in *";__sakura_precmd;"*) ;;
                *) PROMPT_COMMAND="__sakura_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;; esac
        fi
    fi
fi
