from wagtail.models import Site


def navigation(request):
    """Корневые разделы сайта для навигации в header."""
    site = Site.find_for_request(request)
    root = site.root_page if site else None
    nav_items = (
        root.get_children().live().in_menu().specific() if root else []
    )
    return {
        "nav_items": nav_items,
        "root_page": root,
    }
