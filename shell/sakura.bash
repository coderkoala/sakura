# shellcheck shell=bash
# Source this from ~/.bashrc for Sakura's keys:
#   ?  open Sakura           ??  a coordinator with workers
#   ? alone shows the three most likely things first (1-3 does one, Enter opens Sakura; sakura-suggest off stops it)
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
#   ?pr [words]  a pull request from this branch, body from the diff;  ?review [PR|range] [--post]  findings, ranked
#   look FILE|screen|clip [question]  eyes: a local vision model, or --text for OCR
#   ?try [lang] question   a scratch directory, run a snippet, keep nothing
#   ?hear   speak a request instead of typing it;  ?morning  the day on one screen (also shown at the first ? of the day)
#   ?red TEST|"sentence"   red to green: a failing test (or one written from a sentence) made to pass
#   ?decide "what: why"   record a decision where you are;  ?why [words]  find one later
#   ?setup [words]   a new machine set up the way you like, from the dotfiles and memory
#   ?on HOST [request]   a session that lives on another machine (every command over ssh);  logs HOST  errors as a table
#   ?explain [question]  explain what's on the screen (tmux) or in the pipe:  make 2>&1 | ?explain
#   ?how what you want   the one command, printed, not run (-r runs it after a y/n)
#   cmd | ? "question"   anything piped into ? arrives under the request
#   ?watch [-n S] [--explain] 'cmd'   rerun a command, show what changed; --explain has Sakura explain each change
#   sakura-tmux-setup   prefix-? popup, prefix-/ explain the pane, status line
#   ?fmt [--check|--lint]   format and lint what you changed, right tool per language
#   ?gpu   GPU doctor: Xids, heat, throttle, who holds the VRAM, what fits now  (sakura-gpu doctor|free|fit|scale|watch)
#   ?drive put FILE gdrive:folder  |  drive sync ~/p gdrive:p --until midnight   (Google, OneDrive, Dropbox via rclone)
#   ?backup run NAME | prove NAME   backups on restic, proven by restoring a real file (sakura-backup --help)
#   ?dl URL [--sha256 HEX]  resumable download in the background; dl watch, dl stop/resume ID
#   torrent add "magnet:..."  |  torrent watch   downloads over transmission, notification when done
#   ports [PORT|HOST]  what's listening and who holds it;  space [clean [--go]]  what's eating the disk, and the safe set to clear
#   drift FILE|packages|units|sshkeys [HOST...]  how the machines differ;  when "0 3 * * 1"  a cron/OnCalendar line in English, next runs
#   conv FILE --to EXT | merge|split|pages|rotate|compress|ocr|unlock|strip|trim|audio|gif|extract   every conversion, locally, never a website
#   vid URL | vid archive URL | vid watch URL   your own videos kept with their metadata; a channel or playlist, resumable; what's new
#   faces index DIR | people | name ID "Grandma" | find "Grandma"   who is in your photos, found and kept here
#   restore photo.jpg | clip.mp4 [--denoise 0.5] [--smooth]   old photos, scans and video sharpened (Real-ESRGAN, RIFE; restore install once)
#   conv subs VIDEO [--lang ne] [--burn]  subtitles from the speech;  translate "text"|FILE.srt --to ne|hi|en   offline (Argos)
#   money import bank.csv | month | where "KFC" | rule "KFC" expenses:food   statements into plain-text accounting (hledger)
#   dupes DIR... [--link|--rm --go]  the same file by content, across drives;  shelve DIR --into LIB [--go]  photos/videos into YEAR/YEAR-MM by date taken
#   sakura-skill keep NAME steps.md --about "when" | import ~/.claude/skills   know-how kept as a skill; imports are scanned first
#   sakura-lean on|off|status   a tool reference 63% shorter on every turn; a topic's section arrives with the message about it
#   sakura-doctor [--fix]  is this install whole: every command, hook and config checked, what's missing
#   ?last [N] | ?last --here   what was I doing: the last turn's directory, ask and answer, from the record (cd's there)
#   Tab completes every command's subcommands and flags (sakura-complete, generated from the manuals)
#   sakura-model pick [ROLE]   which model does each job: agent, fast, vision, embed, consult roles, the driver; whatmodel.sh in the menu
#   ?what [words]   which command does this? (no model; alone: everything, by situation);  ?docs <question>  your docs packs and documents
#   ?otp NAME   a 2FA code from pass;  vault get NAME  the password onto the clipboard;  vault import bitwarden export.json
#   sakura-notes [TAG]  release notes from the commits since the last tag (for sakura-release)
#   sakura-status   one line for tmux's status bar: driver, night queue, offers, guardian
#   ?go [request]  a session that doesn't stop to ask (sakura-trust on makes every ? like this)
if command -v sakura-launch >/dev/null 2>&1; then
    unalias '?' '??' '?pa' '?remind' '?fix' '?undo' '?recap' '?receipts' '?recall' '?tour' '?tonight' '?teach' '?learn' '?guard' '?go' '?pr' '?review' '?try' '?hear' '?morning' '?red' '?decide' '?why' '?setup' '?on' '?explain' '?how' '?what' '?docs' '?otp' '?last' '?watch' '?fmt' '?gpu' '?drive' '?dl' '?backup' 2>/dev/null
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
    alias '?pr'='sakura-pr'
    alias '?try'='sakura-try'
    alias '?red'='sakura-red'
    alias '?decide'='sakura-decide'
    alias '?setup'='sakura-setup'
    alias '?on'='sakura-on'
    alias '?explain'='sakura-explain'
    alias '?how'='sakura-how'
    __sakura_last() { case "${1:-}" in "" | [0-9]*)
        local d
        d="$(sakura-last --cd 2>/dev/null)" && [ -d "$d" ] && cd "$d"
        sakura-last "$@"
        ;;
    *) sakura-last "$@" ;; esac }
    alias '?last'='__sakura_last'
    alias '?what'='sakura-what'
    alias '?docs'='rag search'
    alias '?otp'='vault otp'
    alias '?watch'='sakura-watch'
    alias '?fmt'='fmt'
    alias '?gpu'='sakura-gpu'
    alias '?drive'='drive'
    alias '?dl'='dl'
    alias '?backup'='sakura-backup'
    alias '?why'='sakura-decide why'
    alias '?morning'='sakura-morning'
    __sakura_hear() {
        local t
        t="$(hear "$@")" || return 1
        printf 'heard: %s\n' "$t"
        sakura-launch "$t"
    }
    alias '?hear'='__sakura_hear'
    alias '?review'='sakura-review'
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
            '?remind '* | '?pa '* | '?fix '* | '? '* | '?? '* | '?learn '* | '?teach '* | '?tour '* | '?recall '* | '?go '* | '?pr '* | '?try '* | '?red '* | '?decide '* | '?why '* | '?setup '* | '?explain '* | '?how '*) ;;
            *) return 0 ;;
        esac
        head=${READLINE_LINE%% *}
        rest=${READLINE_LINE#* }
        case "$rest" in \'*\' | \"*\") return 0 ;; esac # you already quoted it
        printf -v rest '%q' "$rest"
        READLINE_LINE="$head $rest"
        READLINE_POINT=${#READLINE_LINE}
    }
    if [[ $- == *i* ]] && [ -n "${BASH_VERSION:-}" ]; then
        bind -x '"\C-x\C-q": __sakura_quote_line' 2>/dev/null
        bind '"\C-m": "\C-x\C-q\C-j"' 2>/dev/null
        # ?on and logs complete host names from ssh's config; ?tonight, ?guard and pa complete their subcommands.
        __sakura_hosts() { awk 'tolower($1)=="host"{for(i=2;i<=NF;i++) if($i !~ /[*?]/) print $i}' ~/.ssh/config ~/.ssh/config.d/* "${DOTFILES:-$HOME/dotfiles}/ssh/hosts" 2>/dev/null | sort -u; }
        _sakura_host_comp() { COMPREPLY=($(compgen -W "$(__sakura_hosts)" -- "${COMP_WORDS[COMP_CWORD]}")); }
        complete -F _sakura_host_comp '?on' sakura-on logs 2>/dev/null
        complete -W 'list cancel at report run' '?tonight' sakura-tonight 2>/dev/null
        complete -W 'on off tick backup restored forget --all --json' '?guard' sakura-guardian 2>/dev/null
        complete -W 'remind list cancel brief standup roles todo clock log watch job autoreply mail offer yes no listen pending' pa 2>/dev/null
        # every other command: subcommands and flags learned from the manuals (hosts and the keys included)
        command -v sakura-complete >/dev/null 2>&1 && eval "$(sakura-complete 2>/dev/null)"
        # Whatever came due while no notification could reach you.
        command -v pa >/dev/null 2>&1 && pa pending 2>/dev/null
        # The day on one screen, once a day, when the first shell of the day opens.
        command -v sakura-morning >/dev/null 2>&1 && sakura-morning --once 2>/dev/null

        # ?fix: remember the last command that failed, where, and how, so `?fix` needs no copying or explaining.
        # Ctrl-C (130) isn't a failure. Inside tmux the screen is kept too; otherwise ?fix reruns it when that's harmless.
        __sakura_preexec() { __sakura_cmd=$1; }
        __sakura_precmd() {
            local rc=$? dir="${XDG_RUNTIME_DIR:-/tmp}/sakura-fix-$UID" cmd
            if [ -n "${__bp_imported:-}" ]; then
                cmd=${__sakura_cmd:-}
                __sakura_cmd=
            else
                cmd=$(HISTTIMEFORMAT='' history 1)
                cmd=${cmd#*[0-9]  }
            fi
            case "$rc:$cmd" in 0:* | 130:* | *: | *:'?'*) return "$rc" ;; esac
            (
                umask 077
                mkdir -p "$dir" && printf '%s\n%s\n%s\n%s\n' "$rc" "$(date +%s)" "$PWD" "$cmd" >"$dir/$$"
                if [ -n "${TMUX:-}" ]; then tmux capture-pane -p -S -120 >"$dir/$$.screen" 2>/dev/null; else rm -f "$dir/$$.screen"; fi
            )
            return "$rc"
        }
        if [ -n "${__bp_imported:-}" ]; then
            preexec_functions+=(__sakura_preexec)
            precmd_functions+=(__sakura_precmd)
        else
            case ";${PROMPT_COMMAND:-};" in *";__sakura_precmd;"*) ;;
            *) PROMPT_COMMAND="__sakura_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;; esac
        fi
    fi
fi
