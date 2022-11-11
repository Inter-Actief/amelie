from jsonrpc import jsonrpc_method

from amelie.personal_tab.models import Category, Article


@jsonrpc_method('getItems() -> Array', authenticated=False)
def getItemStream(request):
    result = []
    categories = Category.objects.all()
    for category in categories:
        categorydict = ({
            "category": category.name,
            "category-image": category.image,
            "items": []
        })
        articles = Article.objects.filter(category=category)
        for article in articles:
            categorydict["items"].append({
                "name": article.name,
                "price": article.price,
                "article-image": article.image
            })
        result.append(categorydict)
    return result
