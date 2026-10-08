from django.core.management.base import BaseCommand

from wagtail.models import Page


class Command(BaseCommand):
    help = "Search published pages by query and print results to console."

    def add_arguments(self, parser):
        parser.add_argument(
            "query",
            type=str,
            help="Search query, e.g. \"college schedule\"",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            default=10,
            help="Max number of page results to print (default: 10)",
        )

    def handle(self, *args, **options):
        query = options["query"]
        page_size = options["page_size"]

        self.stdout.write(
            self.style.SUCCESS(f"Searching pages for: {query!r}")
        )

        pages = Page.objects.live().search(query)

        if not pages:
            self.stdout.write("No pages found.")
            return

        for page in pages[:page_size]:
            self.stdout.write(f"- {page.title} (id={page.id})")
            self.stdout.write(f"  URL: {page.url}")
