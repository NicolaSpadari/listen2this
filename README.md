<h1 align="center">listen2this</h1>

> This is s WIP

## About

listen2this is a python script that creates automatic playlists on Spotify based on top monthly recommendations by the subreddit r/listentothis.

The cover image is choosen by the top monthly picture from r/earthporn and edited with the month text.

This script is intended to be put into a cronjob and executed monthly

## Setup

- Clone repository
- Create Spotify developer app
- `cp .env.example .env`
- Edit env variables to reflect generated ones
- run `python main.py`

## Todo
- Improve codebase
- Authorize with better flow
- Make it work seamlessly inside a docker container