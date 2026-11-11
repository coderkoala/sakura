# Real-world passes

The evals prove features against local fixtures (GreenMail for mail, a local page for the CAPTCHA hand-off, one machine).
The roadmap's "real-world passes" are the same features against the real thing. Each pass below is a checklist a person
runs once per release that touches the feature, because each needs an account, a second machine, or a human in front of
a browser. Record results in this file's table, dated, and move anything broken into the handoff.

## 1. Mail against a real provider

Needs: a real mailbox for testing (a Gmail with an app password, or any IMAP/SMTP account). Never the main account.

```bash
sakura-mail-setup                 # point himalaya at the test account; password into pass, never a file
himalaya envelope list            # 1. reading works
? "summarise my unread mail"      # 2. the session reads it (and only reads)
? "draft a reply to the newest message saying I'll answer tomorrow; show me, don't send"
                                  # 3. it must STOP at the draft (the guard's DRAFT_NO); send it yourself with q
pa mail-at "in 2 minutes" to YOU@test subject "pa mail-at pass" body "sent by the scheduler"
                                  # 4. arrives on time, from the right account
pa autoreply on "away until Monday" && himalaya message compose --to YOU@test --subject hi --body hi --send
                                  # 5. from ANOTHER account, mail the test account: exactly one auto-reply, none to a newsletter
pa autoreply off
```

Pass: all five, with nothing sent that you didn't see first. Gmail notes: IMAP on, an app password (2FA account), and
expect the first login to trip a security prompt in the web UI. OAuth-only providers (outlook.com business tenants)
aren't supported yet; that's the open item.

## 2. A real CAPTCHA, in the shared browser

Needs: you at the screen. Any site that shows one (a login page behind Cloudflare does).

```bash
? "open https://SITE in the browser and log me in as USER"
```

Pass: when the check appears, Sakura says NEEDS THE USER and stops (no retry, no workaround); you clear it by hand; you
say "done" and it carries on with `sakura-browser read`. Fail: any attempt to solve, reload around, or switch user agent.

## 3. A second device, end to end

Needs: another machine from the fleet (laptop or server), ssh reachable.

```bash
# on the second machine
git clone <dotfiles> && cd dotfiles && ./bootstrap.sh      # or your usual path
sakura-model plan                  # says what that hardware runs and why
? "what machine is this and what's installed"              # the driver or the 9b answers
sakura-web-setup                   # search and the browser, per device
# back on the first machine
fleet                              # the new device shows up, with RAM/GPU
?on NEWHOST check the logs and show me the errors as a table
```

Pass: install completes without hand-editing; `?` answers on the right model for that hardware; `fleet` sees it;
`?on` works against it. Record the hardware and which model `sakura-model plan` chose.

## 4. Reminders across devices

Decided and built: the schedule is shared through whatever syncs `~/.sakura/pa`, a due item is claimed by one machine
(`claims/ID@WHEN.HOST.json`), and the rest stand down when the claim reaches them. `evals/pa_devices.py` proves the rules
with two processes and a copy step standing in for the sync. What it can't prove is your sync's real delay:

```
# on two machines that sync ~/.sakura/pa, both logged in
pa devices                               # each lists the other within an hour of its first tick
pa remind in 5 minutes two-machine test  # on the one you're at
# five minutes later: it shows on this machine only
pa list --fired                          # on the other, after a sync: "fired … on <this machine>"
pa remind every 2 minutes repeat test    # leave it ten minutes, then: pa list --fired | grep -c "repeat test"
pa linger                                # exit 0 on every machine that should fire while logged out
```

Pass: one notification per occurrence across both machines; `pa list --fired` names one host per occurrence. If the
second machine fires too, time how long a file takes to cross (`touch ~/.sakura/pa/x` here, watch for it there) and set
`pa set stagger MINUTES` a little above that; with the git-based dotfiles sync that is its timer interval. Record the
sync used, its delay, and the stagger that gave zero duplicates over a day.

## Results

| Date | Pass | Device/account | Result |
|---|---|---|---|
| 2026-11-07 | Mail (GreenMail only) | local fixture | 21/22, known "told to send" miss |
| | Mail, real provider | | not yet run |
| | CAPTCHA, real site | | not yet run |
| | Second device | | not yet run |
