function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-bg-${type} border-0 mb-2" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>`;
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = document.getElementById(toastId);
    if (toastEl) {
        new bootstrap.Toast(toastEl, { delay: 3500 }).show();
    }
}

async function addToCart(productId, quantity = 1) {
    const response = await fetch('/add-to-cart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId, quantity }),
    });
    const result = await response.json();
    if (result.success) {
        showToast(result.message, 'success');
    } else {
        showToast(result.message || 'Unable to add product.', 'danger');
        if (response.status === 401) {
            setTimeout(() => { window.location.href = '/login'; }, 1200);
        }
    }
}

function renderProducts(products) {
    const grid = document.getElementById('productsGrid');
    const noProducts = document.getElementById('noProducts');
    if (!grid) return;
    grid.innerHTML = '';
    if (!products.length) {
        noProducts.classList.remove('d-none');
        return;
    }
    noProducts.classList.add('d-none');
    products.forEach(product => {
        const col = document.createElement('div');
        col.className = 'col-md-4';
        col.innerHTML = `
            <div class="card h-100 shadow-sm">
                <img src="${product.image_url}" class="card-img-top" alt="${product.name}">
                <div class="card-body d-flex flex-column">
                    <h5 class="card-title">${product.name}</h5>
                    <p class="card-text text-muted">${product.category}</p>
                    <p class="card-text small">${product.description.length > 100 ? product.description.slice(0, 100) + '...' : product.description}</p>
                    <div class="mt-auto d-flex justify-content-between align-items-center">
                        <span class="h5 text-success">$${product.price.toFixed(2)}</span>
                        <div>
                            <a href="/product/${product.id}" class="btn btn-sm btn-outline-success me-2">Details</a>
                            <button class="btn btn-sm btn-success" onclick="addToCart(${product.id})">Add</button>
                        </div>
                    </div>
                </div>
            </div>`;
        grid.appendChild(col);
    });
}

async function fetchProducts() {
    const response = await fetch('/api/products');
    if (!response.ok) return [];
    return response.json();
}

async function loadProductGrid() {
    const allProducts = await fetchProducts();
    const searchInput = document.getElementById('searchInput');
    const categorySelect = document.getElementById('categorySelect');
    function filterProducts() {
        const query = searchInput.value.trim().toLowerCase();
        const category = categorySelect.value;
        const filtered = allProducts.filter(product => {
            const matchSearch = product.name.toLowerCase().includes(query) || product.description.toLowerCase().includes(query);
            const matchCategory = !category || product.category === category;
            return matchSearch && matchCategory;
        });
        renderProducts(filtered);
    }
    searchInput?.addEventListener('input', filterProducts);
    categorySelect?.addEventListener('change', filterProducts);
    filterProducts();
}

async function loadCartPage() {
    const cartContent = document.getElementById('cartContent');
    if (!cartContent) return;
    const response = await fetch('/api/cart');
    if (!response.ok) {
        cartContent.innerHTML = '<div class="alert alert-danger">Unable to load cart. Please login.</div>';
        return;
    }
    const data = await response.json();
    if (!data.items.length) {
        cartContent.innerHTML = '<div class="alert alert-info">Your cart is empty. Browse our <a href="/products" class="alert-link">products</a>.</div>';
        return;
    }
    const rows = data.items.map(item => `
        <tr>
            <td><img src="${item.image_url}" alt="${item.name}" class="img-fluid rounded" style="width: 80px; height: 80px; object-fit: cover;"></td>
            <td>${item.name}</td>
            <td>$${item.price.toFixed(2)}</td>
            <td><input type="number" class="form-control quantity-input" data-cart-id="${item.cart_id}" value="${item.quantity}" min="1" style="width: 90px;"></td>
            <td>$${item.subtotal.toFixed(2)}</td>
            <td><button class="btn btn-sm btn-outline-danger remove-item" data-cart-id="${item.cart_id}">Remove</button></td>
        </tr>`).join('');
    cartContent.innerHTML = `
        <div class="table-responsive">
            <table class="table align-middle">
                <thead class="table-light">
                    <tr>
                        <th>Image</th>
                        <th>Product</th>
                        <th>Price</th>
                        <th>Qty</th>
                        <th>Subtotal</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-3 mt-4">
            <a href="/checkout" class="btn btn-success btn-lg">Proceed to Checkout</a>
            <div class="d-flex justify-content-end align-items-center gap-3 mt-2 mt-md-0">
                <h4 class="mb-0">Total:</h4>
                <span class="h4 text-success mb-0">$${data.total.toFixed(2)}</span>
            </div>
        </div>
    `;
    document.querySelectorAll('.quantity-input').forEach(input => {
        input.addEventListener('change', async () => {
            const cartId = input.dataset.cartId;
            const quantity = parseInt(input.value, 10) || 1;
            const update = await fetch('/api/update-cart-quantity', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ cart_id: cartId, quantity }),
            });
            if (update.ok) {
                showToast('Cart updated successfully.');
                loadCartPage();
            } else {
                showToast('Could not update quantity.', 'danger');
            }
        });
    });
    document.querySelectorAll('.remove-item').forEach(button => {
        button.addEventListener('click', async () => {
            const cartId = button.dataset.cartId;
            const removed = await fetch('/api/remove-cart-item', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ cart_id: cartId }),
            });
            if (removed.ok) {
                showToast('Item removed from cart.', 'info');
                loadCartPage();
            }
        });
    });
}

function setupProductDetails() {
    const addToCartBtn = document.getElementById('addToCartBtn');
    if (!addToCartBtn) return;
    addToCartBtn.addEventListener('click', () => {
        const productId = addToCartBtn.dataset.productId;
        const quantity = parseInt(document.getElementById('quantitySelect').value, 10) || 1;
        addToCart(productId, quantity);
    });
}

function setupForms() {
    document.querySelectorAll('.needs-validation').forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    setupForms();
    setupProductDetails();
    if (document.getElementById('productsGrid')) {
        loadProductGrid();
    }
    if (document.getElementById('cartContent')) {
        loadCartPage();
    }
});
