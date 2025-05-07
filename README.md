# Blind Vote

Set up a votation and stores secret shares of the vote in nilDB

# How to use

## Installation
First install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:
```shell
# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate
```

Then follow the local installation:
```shell
# Install package in development mode
uv pip install -e .
```

```shell
# Install flask and flask-core
uv pip install flask
uv pip install flask-cors
```

## Setting up the App

First follow these two steps:
- Register a new organization in Nillion's [SecretVault Registration
Portal](https://sv-sda-registration.replit.app/).
- After you get your nilDB credentials, copy `.bvote_config.sample.json` to `.bvote_config_voting.json` and store your credentials.
- **Note:** If you haven't configured your schemas yet, you can safely disregard the following: `SCHEMA_ID` and `BEARER_TOKEN`.

```shell
# Run backend
uv run backend/app.py
```

This is will set up the webApp

## Vote Manager

Once the the APP is set up, the vote manager can setup the Voting.

- Write the question of the voting
- Write the numbers of options the voting has.
- Press `Start Setup`
- Write the name of each option.
- Press `Confirm Options` if you want to finish setting up the vote or presse `Restart Setup` in case you want to change the setup
- Then press `Copy Voting Link` and share it with the voters.
- Press `End Voting` to stop the vote.

## Voter

Once you are given the voting link do:

- Write your `Voter_id`
- Select one of the voting options
- Press `Submit Your Vote`
- Wait to get the final results once the voting is over.





