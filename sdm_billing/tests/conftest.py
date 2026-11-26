import os
import pytest

# Ensure tests run against local test database and do not mutate live Supabase production data
os.environ["TESTING"] = "1"
