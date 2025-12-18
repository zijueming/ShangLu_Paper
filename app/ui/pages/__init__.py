from .account import render_account
from .admin import render_admin
from .auth import render_login, render_register
from .home import render_home
from .job import render_job
from .landing import render_landing
from .relationship import render_relationship
from .tags import render_tags
from .draw import render_draw
from .translate import render_translate
from .weekly import render_weekly

__all__ = [
    "render_account",
    "render_admin",
    "render_draw",
    "render_home",
    "render_job",
    "render_landing",
    "render_login",
    "render_register",
    "render_relationship",
    "render_tags",
    "render_translate",
    "render_weekly",
]
