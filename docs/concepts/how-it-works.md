# How It Works

This is the short version of a JOSSeph run.

1. JOSSeph reads your config.
2. It reads the repository list file.
3. It decides which tools to run.
4. It processes repositories in parallel.
5. It writes a result file for each successful tool.
6. It writes one summary file for the whole run.

What matters for you:

- you control the repositories in a text file
- you choose the tools in the YAML config
- you read the output from `results/`
- you use `summary.json` to see what happened

## When a tool fails

If one tool fails for one repository, JOSSeph keeps going for the rest of the
run. The failure is recorded in the summary.

## When the run stops early

The run stops before analysis if the config is invalid or a required file is
missing.
