from django.db import models

from users.models import CustomUser



class MainCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name_plural = 'Main Categories'

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    name = models.CharField(max_length=100)
    main_category = models.ForeignKey(MainCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')


    class Meta:
        verbose_name_plural = 'Product Categories'

    def __str__(self):
        return f"{self.name} ({self.main_category})" if self.main_category else self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    calories = models.PositiveIntegerField(default=0, null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.category}"


class Basket(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    products = models.ManyToManyField(Product, through="BasketItem")


class BasketItem(models.Model):
    basket = models.ForeignKey(Basket, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0)


class Shop(models.Model):
    name = models.CharField(max_length=75)

    def __str__(self):
        return self.name


class Shopping(models.Model):

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_shopping', null=True, blank=True, default=None)
    date = models.DateField()  # Example field to track shopping date
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True)

    def total_amount(self):
        return sum(sp.amount for sp in self.shopping_products.all())

    def total_discount(self):
        return sum(sp.discount for sp in self.shopping_products.all())

    def __str__(self):
        return f"{self.shop.name} : {self.date}"


class ShoppingProduct(models.Model):
    shopping = models.ForeignKey(Shopping, on_delete=models.CASCADE, related_name="shopping_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1.00)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0.00)

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.price - self.discount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} in Shopping {self.shopping.id}"


class ShoppingList(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    date_generated = models.DateField(auto_now_add=True)  # Auto-fill when created
    sent = models.BooleanField(default=False)  # Track whether list was emailed
    items = models.JSONField(default=list)

    def __str__(self):
        return f"Shopping List for {self.user.username} - {self.date_generated}"


class RecipeShoppingList(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    recipe_name = models.CharField(max_length=150)  # ✅ Stores the recipe name
    sent = models.BooleanField(default=False)
    items = models.JSONField(default=list)  # ✅ Stores missing products as a list of names

    def __str__(self):
        return f"Shopping List for {self.user.username} - {self.recipe_name}"