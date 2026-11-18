import os
from server import app
from core import register

# The static files now live in public/static, so Vercel can serve them.
app.static_folder = os.path.join(app.root_path, "public", "static")
register(app)

if __name__ == "__main__":
    app.run(port=5000, debug=False)