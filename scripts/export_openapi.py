#!/usr/bin/env python
import json
from app.main import app

def main():
    spec = app.openapi()
    print(json.dumps(spec, indent=2))

if __name__ == "__main__":
    main()

