# GTA VI launch-day Twitch CCU forecaster

Entry for [make.fun/gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01).

Forecasts hourly Twitch concurrent viewers for Grand Theft Auto VI's release day
(2026-11-19 UTC), hours 2-24, as five quantiles per hour, from hour 1's print plus
comparable past launches' curves. Ranks by mean pinball loss on the log scale.

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Run: `MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py`
