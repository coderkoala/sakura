# shellcheck shell=bash
# Source this from ~/.bashrc for Sakura's keys:
#   ?  open Sakura           ??  a coordinator with workers
#   ?remind tomorrow, 10am birthday wish
#   ?pa reply to all my emails saying I'm busy
#   ?fix  fix the command that just failed (words after it are a hint)
#   ?undo put back everything Sakura's last turn changed (again: redo)
#   ?recap what Sakura did today, from the record (yesterday, week, 3d, a date; --full)
#   ?receipts  the same, every command (the audit trail)
#   ?recall <words>  search past conversations
#   ?tour [PATH] [question]  any codebase in five minutes, cited
#   ?tonight <<'JOB' ... JOB   queue work for the night shift; ?tonight list / report
#   ?teach [words]  turn what you just did in the shell into a kept tool or a scheduled job
#   ?learn <topic>  a mentor's explanation, at your level
#   ?guard  what's about to hurt: disks, certs, failed units, backups
#   ?go [request]  a session that doesn't stop to ask (sakura-trust on makes every ? like this)
if command -v sakura-launch >/dev/null 2>&1; then
    unalias '?' '??' '?pa' '?remind' '?fix' '?undo' '?recap' '?receipts' '?recall' '?tour' '?tonight' '?teach' '?learn' '?guard' '?go' 2>/dev/null
    alias '?'='sakura-launch'
    alias '?fix'='sakura-fix --shell $$'
    alias '?undo'='sakura-undo'
    alias '?recap'='sakura-recap'
    alias '?receipts'='sakura-recap --full'
    alias '?recall'='sakura-recall'
    alias '?tour'='sakura-tour'
    alias '?tonight'='sakura-tonight'
    alias '?learn'='sakura-learn'
    alias '?guard'='sakura-guardian'
    alias '?go'='SAKURA_TRUST=1 sakura-launch'
    # ?teach hands Sakura your recent commands, so there's nothing to paste.
    __sakura_teach() { HISTTIMEFORMAT='' history 40 | sakura-teach --history - "$@"; }
    alias '?teach'='__sakura_teach'
    alias '??'='sakura-launch --coordinator'
    alias '?remind'='pa remind'
    alias '?pa'='pa ask'

    # What you type after these is a sentence, not shell. "I'm busy (idk)" would otherwise be a syntax error before anything
    # could run, so Enter quotes the sentence first. Only lines that start with one of these keys are touched.
    __sakura_quote_line() {
        local head rest
        case "$READLINE_LINE" in
            '?remind '*|'?pa '*|'?fix '*|'? '*|'?? '*|'?learn '*|'?teach '*|'?tour '*|'?recall '*|'?go '*) ;;
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
