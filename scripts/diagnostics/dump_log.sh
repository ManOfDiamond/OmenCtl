#!/bin/bash
tmp_log=$(mktemp /tmp/git_log.XXXXXX)
git log -n 10 > "$tmp_log"
echo "Log saved to: $tmp_log"
