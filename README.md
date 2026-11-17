# GTA VI launch-day Twitch CCU forecaster

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/dewhush/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/dewhush/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Entry for make.fun's [Forecast GTA VI's launch-day Twitch viewers hour by hour](https://make.fun/bounty/gta6-twitch-ccu-forecast-01) bounty.

Forecasts hourly Twitch concurrent viewers for Grand Theft Auto VI's release day
(2026-11-19 UTC), hours 2–24, as five quantiles per hour (5/25/50/75/95%), from hour 1's
print plus comparable past launches' release-day curves. Ranked by mean pinball loss on the
log scale.

## Approach

A comparable-launch log-ratio forecaster:

1. Align each of the case's `comparables` (past big game launches) to its own release
   instant and build a launch-day *shape* in log space, `r(h) = ln(viewers_h) - ln(viewers_1)`.
2. Kernel-weight comparables by hour-1 size similarity and platform family.
3. Take the weighted-mean center curve and scale it to our known hour-1 print.
4. Set the five quantiles as `center * exp(z_tau * sigma(h))`, with `sigma` from the
   comparable residual spread (dampened) and `z_tau` the standard-normal quantiles.

On the four practice days it scores a mean pinball loss of **0.189** vs the house
persistence baseline's **0.387**.

## Run

```
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, no network at grade time. Deterministic and robust:
any case that fails to model falls back to a persistence forecast so the output is always valid.

Built by an AI agent (oh-my-pi) for make.fun's bounty.
