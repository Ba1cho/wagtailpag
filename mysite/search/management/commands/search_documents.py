from django.core.management.base import BaseCommand

from search.views import search_documents


class Command(BaseCommand):
    help = (
        "Search documents and pages that reference them, using the same logic "
        "as the public search page."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "query",
            type=str,
            help="Search query, e.g. \"library brochure\"",
        )
        parser.add_argument(
            "--max-results",
            type=int,
            default=50,
            help="Max number of document results to print (default: 50)",
        )

    def handle(self, *args, **options):
        query = options["query"]
        max_results = options["max_results"]

        self.stdout.write(
            self.style.SUCCESS(f"Searching documents for: {query!r}")
        )

        results = search_documents(query)

        if not results:
            self.stdout.write("No document results found.")
            return

        for item in results[:max_results]:
            document = item["document"]
            pages = item["pages"]

            self.stdout.write(
                self.style.SUCCESS(f"\nДокумент: {document.title} (id={document.pk})")
            )

            if document.file:
                self.stdout.write(f"  File: {document.file.name}")
            else:
                self.stdout.write("  File: <no file>")

            self.stdout.write(f"  Linking pages: {len(pages)}")
            for page in pages:
                self.stdout.write(f"    - {page.title} (id={page.id})")
