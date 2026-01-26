// ============================================
// GLOBAL VARIABLES
// ============================================
let currentPage = 1;
let currentFilters = {};
let isChatLoading = false;
let currentSessionId = null;
let conversationTurnCount = 0;

// ============================================
// CHAT FUNCTIONS
// ============================================

function toggleChat() {
  const chatSidebar = document.getElementById("chatSidebar");
  if (chatSidebar) {
    chatSidebar.classList.toggle("open");
    if (chatSidebar.classList.contains("open")) {
      setTimeout(() => {
        const chatInput = document.getElementById("chatInput");
        if (chatInput) chatInput.focus();
      }, 300);
    }
  }
}

async function sendChatMessage() {
  const chatInput = document.getElementById("chatInput");
  const chatMessages = document.getElementById("chatMessages");
  const followUpQuestions = document.getElementById("followUpQuestions");
  const chatSendBtn = document.getElementById("chatSendBtn");

  if (!chatInput || !chatMessages) return;

  const query = chatInput.value.trim();
  if (!query || isChatLoading) return;

  if (followUpQuestions) followUpQuestions.innerHTML = "";
  addChatMessage(query, "user");
  chatInput.value = "";

  isChatLoading = true;
  chatInput.disabled = true;
  if (chatSendBtn) chatSendBtn.disabled = true;

  const loadingId = addChatMessage("", "bot", true);

  try {
    // Ensure we have a session before sending
    if (!currentSessionId) {
      await createNewSession();
    }

    const response = await fetch("/api/v1/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: query,
        session_id: currentSessionId
      }),
    });

    const data = await response.json();
    removeChatMessage(loadingId);

    if (data.success) {
      // Save session_id for subsequent requests
      if (data.session_id && !["stateless", "string", "null"].includes(data.session_id.toLowerCase())) {
        currentSessionId = data.session_id;
        conversationTurnCount++;
        updateSessionIndicator();
      }

      addChatMessage(data.response_text, "bot", false, false);

      // NEW: Display recommended products in main catalog if available
      // if (data.recommended_products && data.recommended_products.length > 0) {
      //   displayRecommendedProducts(data.recommended_products);
      //   addChatMessage(
      //     `✨ Showing ${data.recommended_products.length} recommended products in the catalog below`,
      //     "bot",
      //     false,
      //     true
      //   );
      // } else if (data.products && data.products.length > 0) {
      //   // Fallback: show minimal products in chat if no recommendations
      //   addProductsToChat(data.products);
      // }

      // Old
      // NEW CODE - Always show products in chat only
      if (data.recommended_products && data.recommended_products.length > 0) {
        addRecommendedProductsToChat(data.recommended_products);
      } else if (data.products && data.products.length > 0) {
        addProductsToChat(data.products);
      }

      if (data.follow_up_questions && data.follow_up_questions.length > 0) {
        addFollowUpQuestions(data.follow_up_questions);
      }

      // if (data.metadata) {
      //   const metaText = `Found ${data.metadata.total_results || 0} product(s)${
      //     data.metadata.in_stock_count
      //       ? `, ${data.metadata.in_stock_count} in stock`
      //       : ""
      //   }`;
      //   addChatMessage(metaText, "bot", false, true);
      // }
    } else {
      addChatMessage(
        data.error_message || "Sorry, I encountered an error. Please try again.",
        "bot"
      );
    }
  } catch (error) {
    console.error("Chat error:", error);
    removeChatMessage(loadingId);
    addChatMessage(
      "Sorry, I encountered an error. Please check your connection and try again.",
      "bot"
    );
  } finally {
    isChatLoading = false;
    chatInput.disabled = false;
    if (chatSendBtn) chatSendBtn.disabled = false;
    chatInput.focus();
  }
}


function handleChatKeyPress(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendChatMessage();
  }
}

function formatMessageText(text) {
  return text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function addChatMessage(text, type, isLoading = false, isMeta = false) {
  const chatMessages = document.getElementById("chatMessages");
  if (!chatMessages) return null;

  const messageDiv = document.createElement("div");
  const messageId = "msg-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
  messageDiv.id = messageId;
  messageDiv.className = `chat-message ${type}-message`;

  if (isLoading) {
    messageDiv.innerHTML = `
      <div class="message-content">
        <div class="chat-loading">
          <div class="spinner-border spinner-border-sm" role="status"></div>
          <span>Searching products...</span>
        </div>
      </div>
    `;
  } else {
    const icon = type === "bot" ? '<i class="bi bi-robot"></i>' : "";
    const metaClass = isMeta ? "text-muted small" : "";
    const formattedText = type === "bot" ? formatMessageText(escapeHtml(text)) : escapeHtml(text);

    messageDiv.innerHTML = `
      <div class="message-content ${metaClass}">
        ${icon}
        <p>${formattedText}</p>
      </div>
    `;
  }

  chatMessages.appendChild(messageDiv);
  scrollChatToBottom();

  return messageId;
}

function removeChatMessage(messageId) {
  const message = document.getElementById(messageId);
  if (message) {
    message.remove();
  }
}

function addProductsToChat(products) {
  const chatMessages = document.getElementById("chatMessages");
  if (!chatMessages || !products || products.length === 0) return;

  const productsDiv = document.createElement("div");
  productsDiv.className = "chat-message bot-message";

  let productsHtml = '<div class="message-content"><p><strong>Found Products:</strong></p>';

  products.forEach((product) => {
    const featuresHtml =
      product.key_features && product.key_features.length > 0
        ? `<div class="chat-product-features">${product.key_features
            .map((f) => `<span class="badge bg-secondary">${escapeHtml(f)}</span>`)
            .join("")}</div>`
        : "";

    productsHtml += `
      <div class="chat-product-card" onclick="window.open('/product/${product.id}', '_blank')">
        <div class="chat-product-title">${escapeHtml(product.title)}</div>
        <div class="chat-product-price">${escapeHtml(product.price)}</div>
        ${featuresHtml}
      </div>
    `;
  });

  productsHtml += "</div>";
  productsDiv.innerHTML = productsHtml;
  chatMessages.appendChild(productsDiv);
  scrollChatToBottom();
}


function addRecommendedProductsToChat(products) {
  const chatMessages = document.getElementById("chatMessages");
  if (!chatMessages || !products || products.length === 0) return;

  const productsDiv = document.createElement("div");
  productsDiv.className = "chat-message bot-message";

  let productsHtml = `
    <div class="message-content">
      <p><strong>✨ Recommended Products:</strong></p>
  `;

  products.forEach((product) => {
    const stockBadgeClass = {
      "In Stock": "bg-success",
      "Low Stock": "bg-warning",
      "Out of Stock": "bg-danger",
    }[product.stock_status] || "bg-secondary";

    const discountBadge = product.discount_percent
      ? `<span class="badge bg-danger ms-2">${product.discount_percent}% OFF</span>`
      : "";

    const mrpDisplay =
      product.mrp && product.mrp > product.price
        ? `<span class="text-decoration-line-through text-muted small ms-2">₹${product.mrp.toLocaleString()}</span>`
        : "";

    productsHtml += `
      <div class="chat-product-card" onclick="window.open('/product/${product.product_id}', '_blank')">
        <div class="d-flex align-items-start gap-3">
          <img src="${product.primary_image || 'https://via.placeholder.com/80x80?text=No+Image'}" 
               alt="${escapeHtml(product.title)}"
               style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px;"
               onerror="this.src='https://via.placeholder.com/80x80?text=No+Image'">
          <div class="flex-grow-1">
            <div class="chat-product-title">${escapeHtml(product.title)}</div>
            <div class="text-muted small mb-1">
              <i class="bi bi-tag"></i> ${escapeHtml(product.brand || "Unknown Brand")}
            </div>
            <div class="mb-2">
              <span class="badge ${stockBadgeClass}">${product.stock_status || "Unknown"}</span>
              ${discountBadge}
            </div>
            <div class="chat-product-price">
              ₹${product.price.toLocaleString()} ${mrpDisplay}
            </div>
          </div>
        </div>
      </div>
    `;
  });

  productsHtml += "</div>";
  productsDiv.innerHTML = productsHtml;
  chatMessages.appendChild(productsDiv);
  scrollChatToBottom();
}

function addFollowUpQuestions(questions) {
  const followUpContainer = document.getElementById("followUpQuestions");
  if (!followUpContainer || !questions || questions.length === 0) return;

  followUpContainer.innerHTML = '<small class="text-muted d-block mb-2">Suggested questions:</small>';

  questions.forEach((question) => {
    const span = document.createElement("span");
    span.className = "follow-up-tag";
    span.textContent = question;
    followUpContainer.appendChild(span);
  });
}

function scrollChatToBottom() {
  const chatMessages = document.getElementById("chatMessages");
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ============================================
// SESSION MANAGEMENT FUNCTIONS
// ============================================

function updateSessionIndicator() {
  const indicator = document.getElementById("sessionIndicator");
  if (!indicator) return;

  if (currentSessionId && !["stateless", "string", "null"].includes(currentSessionId.toLowerCase())) {
    indicator.innerHTML = `
      <div class="session-active text-muted small d-flex align-items-center gap-2">
        <i class="bi bi-chat-dots-fill text-success"></i>
        <span>Turn ${conversationTurnCount}</span>
      </div>
    `;
    indicator.classList.add("active");
  } else {
    indicator.innerHTML = `
      <div class="session-inactive text-muted small">
        <i class="bi bi-chat"></i>
        <span>New Chat</span>
      </div>
    `;
    indicator.classList.remove("active");
  }
}

async function startNewConversation() {
  // Delete old session on backend if it exists
  if (currentSessionId) {
    try {
      await fetch(`/api/v1/sessions/${currentSessionId}`, {
        method: "DELETE"
      });
      console.log("Deleted old session:", currentSessionId);
    } catch (error) {
      console.error("Error deleting session:", error);
    }
  }
  
  // Clear localStorage
  localStorage.removeItem("chatSessionId");
  
  // Create new session
  await createNewSession();
  
  // Clear chat messages
  const chatMessages = document.getElementById("chatMessages");
  if (chatMessages) {
    chatMessages.innerHTML = `
      <div class="chat-message bot-message">
        <div class="message-content">
          <i class="bi bi-robot"></i>
          <p>Hi! I'm your shopping assistant. What are you looking for today?</p>
        </div>
      </div>
    `;
  }
  
  // Clear follow-up questions
  const followUpQuestions = document.getElementById("followUpQuestions");
  if (followUpQuestions) {
    followUpQuestions.innerHTML = "";
  }
  
  // Update session indicator
  updateSessionIndicator();
  
  // Focus on input
  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.value = "";
    chatInput.focus();
  }
  
  console.log("Started new conversation");
}

function initializeSessionUI() {
  updateSessionIndicator();
}

// ============================================
// SESSION CREATION & RESTORATION
// ============================================

async function createNewSession() {
  try {
    const response = await fetch("/api/v1/sessions", {
      method: "POST",
      headers: {"Content-Type": "application/json"}
    });
    
    if (!response.ok) {
      throw new Error("Failed to create session");
    }
    
    const data = await response.json();
    currentSessionId = data.session_id;
    conversationTurnCount = 0;
    
    // Persist to localStorage
    localStorage.setItem("chatSessionId", currentSessionId);
    
    updateSessionIndicator();
    console.log("Created new session:", currentSessionId);
    
    return currentSessionId;
  } catch (error) {
    console.error("Error creating session:", error);
    // Fallback: generate client-side UUID
    currentSessionId = generateClientSideUUID();
    localStorage.setItem("chatSessionId", currentSessionId);
    console.log("Using client-side session ID:", currentSessionId);
    return currentSessionId;
  }
}

async function restoreSession() {
  const savedSessionId = localStorage.getItem("chatSessionId");
  
  if (savedSessionId) {
    try {
      // Verify session still exists on backend
      const response = await fetch(`/api/v1/sessions/${savedSessionId}/history`);
      
      if (response.ok) {
        currentSessionId = savedSessionId;
        const history = await response.json();
        conversationTurnCount = Math.floor(history.length / 2); // Each turn = user + bot message
        
        // Restore chat history in UI
        restoreChatHistory(history);
        updateSessionIndicator();
        
        console.log("Restored session:", currentSessionId, "with", conversationTurnCount, "turns");
        return true;
      } else {
        // Session expired/not found, clear localStorage
        console.log("Session not found on backend, clearing localStorage");
        localStorage.removeItem("chatSessionId");
        return false;
      }
    } catch (error) {
      console.error("Error restoring session:", error);
      localStorage.removeItem("chatSessionId");
      return false;
    }
  }
  
  return false;
}

function restoreChatHistory(history) {
  const chatMessages = document.getElementById("chatMessages");
  if (!chatMessages || !history || history.length === 0) return;
  
  chatMessages.innerHTML = ""; // Clear welcome message
  
  history.forEach(msg => {
    const type = msg.type === "human" ? "user" : "bot";
    addChatMessage(msg.content, type, false, false);
  });
  
  console.log("Restored", history.length, "messages from chat history");
}

function generateClientSideUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// ============================================
// DYNAMIC FILTER FUNCTIONS (FIXED)
// ============================================
async function loadCategories() {
  const categorySelect = document.getElementById("filterCategory");
  if (!categorySelect) return;

  const res = await fetch("/api/v1/categories");
  if (!res.ok) throw new Error("Failed to load categories");

  const categories = await res.json();

  categorySelect.innerHTML = `<option value="">Select Category</option>`;

  categories.forEach((cat) => {
    categorySelect.innerHTML += `
      <option value="${cat.id}">
        ${cat.name}
      </option>
    `;
  });

  if (categories.length > 0) {
    categorySelect.value = categories[0].id;
  }
}

async function loadDynamicFilters(categoryId) {
  const filterContainer = document.getElementById("dynamicFilters");
  if (!filterContainer) return;

  if (!categoryId) {
    filterContainer.innerHTML =
      '<p class="text-muted small">Select a category to see filters.</p>';
    return;
  }

  try {
    const response = await fetch(`/api/v1/filters?category_id=${categoryId}`);
    if (!response.ok) throw new Error("Failed to load filters");

    const data = await response.json();
    filterContainer.innerHTML = "";

    if (!data.filters || data.filters.length === 0) {
      filterContainer.innerHTML =
        '<p class="text-muted small">No filters available.</p>';
      return;
    }

    filterContainer.innerHTML =
      '<hr><h6 class="text-muted mb-3">Product Attributes</h6>';

    data.filters.forEach((filter) => {
      const html = createFilterHTML(filter);
      if (html) filterContainer.innerHTML += html;
    });
    
    // ✅ ADD EVENT LISTENERS TO DYNAMIC FILTERS
    attachDynamicFilterListeners();
  } catch (err) {
    console.error("Filter load error:", err);
    filterContainer.innerHTML =
      '<p class="text-danger small">Error loading filters</p>';
  }
}

// ✅ NEW FUNCTION: Attach change listeners to dynamic filters
function attachDynamicFilterListeners() {
  // Auto-apply on checkbox change
  document.querySelectorAll('input[name^="filter_"][type="checkbox"]').forEach(input => {
    input.addEventListener('change', () => {
      console.log('Checkbox changed:', input.name, input.checked);
    });
  });
  
  // Auto-apply on range input change (with debounce)
  let rangeTimeout;
  document.querySelectorAll('input[name^="filter_"][type="number"]').forEach(input => {
    input.addEventListener('input', () => {
      clearTimeout(rangeTimeout);
      rangeTimeout = setTimeout(() => {
        console.log('Range changed:', input.name, input.value);
      }, 500);
    });
  });
}

function clearDynamicFiltersUI() {
  document.querySelectorAll('input[name^="filter_"]').forEach((input) => {
    if (input.type === "checkbox") input.checked = false;
    if (input.type === "number") input.value = "";
  });
}

function createFilterHTML(filter) {
  switch (filter.filter_type) {
    case "multi_select":
      return createMultiSelectFilter(filter);
    case "range":
      return createRangeFilter(filter);
    case "toggle":
      return createToggleFilter(filter);
    default:
      return "";
  }
}

// ✅ FIXED: Don't normalize values - use original values
function createMultiSelectFilter(filter) {
  if (!filter.options || filter.options.length === 0) return "";

  const displayOptions = filter.options.slice(0, 10);
  const hasMore = filter.options.length > 10;

  return `
    <div class="filter-group mb-3">
      <h6 class="filter-title">${escapeHtml(filter.display_name)}</h6>
      <div class="filter-options">
        ${displayOptions
          .map((opt) => {
            // ✅ Use original value, create safe ID
            const safeId = `filter_${filter.attribute_name}_${opt.value.replace(/[^a-zA-Z0-9]/g, '_')}`;
            
            return `
              <div class="form-check">
                <input class="form-check-input"
                       type="checkbox"
                       name="filter_${filter.attribute_name}"
                       value="${escapeHtml(opt.value)}"
                       id="${safeId}">
                <label class="form-check-label" for="${safeId}">
                  ${escapeHtml(opt.label)}
                  ${opt.count ? `<span class="text-muted small">(${opt.count})</span>` : ""}
                </label>
              </div>
            `;
          })
          .join("")}
        ${
          hasMore
            ? `<button class="btn btn-link btn-sm p-0" onclick="showMoreOptions('${filter.attribute_name}')">Show more…</button>`
            : ""
        }
      </div>
    </div>
  `;
}

function createRangeFilter(filter) {
  if (filter.min_value === null || filter.max_value === null) return "";

  return `
    <div class="filter-group mb-3">
      <h6 class="filter-title">${escapeHtml(filter.display_name)}</h6>
      <div class="row g-2">
        <div class="col-6">
          <input type="number" 
                 class="form-control form-control-sm" 
                 name="filter_${filter.attribute_name}_min"
                 placeholder="Min: ${filter.min_value}"
                 min="${filter.min_value}"
                 max="${filter.max_value}"
                 step="any">
        </div>
        <div class="col-6">
          <input type="number" 
                 class="form-control form-control-sm" 
                 name="filter_${filter.attribute_name}_max"
                 placeholder="Max: ${filter.max_value}"
                 min="${filter.min_value}"
                 max="${filter.max_value}"
                 step="any">
        </div>
      </div>
    </div>
  `;
}

function createToggleFilter(filter) {
  return `
    <div class="filter-group mb-3">
      <div class="form-check form-switch">
        <input class="form-check-input" 
               type="checkbox" 
               name="filter_${filter.attribute_name}"
               id="filter_${filter.attribute_name}">
        <label class="form-check-label" for="filter_${filter.attribute_name}">
          ${escapeHtml(filter.display_name)}
        </label>
      </div>
    </div>
  `;
}

function showMoreOptions(attributeName) {
  console.log("Show more options for:", attributeName);
  // TODO: Implement expand functionality
}

// ============================================
// PRODUCT LISTING FUNCTIONS
// ============================================

async function loadProducts(page = 1) {
  const loadingSpinner = document.getElementById("loadingSpinner");
  const productsGrid = document.getElementById("productsGrid");

  if (!productsGrid) return;

  if (loadingSpinner) loadingSpinner.classList.add("show");
  productsGrid.innerHTML = "";

  const params = new URLSearchParams({
    page: page,
    page_size: 12,
    ...currentFilters,
  });

  console.log('Loading products with filters:', currentFilters);
  console.log('Request URL:', `/products?${params}`);

  try {
    const response = await fetch(`/api/v1/products?${params}`);
    const data = await response.json();

    const productCount = document.getElementById("productCount");
    if (productCount) {
      productCount.textContent = `Showing ${data.products.length} of ${data.total} products`;
    }

    if (data.products.length === 0) {
      productsGrid.innerHTML = `
        <div class="col-12">
          <div class="alert alert-info text-center">
            <i class="bi bi-inbox"></i> No products found. Try adjusting your filters.
          </div>
        </div>
      `;
    } else {
      data.products.forEach((product) => {
        const productCard = createProductCard(product);
        productsGrid.appendChild(productCard);
      });
    }

    updatePagination(data.total, data.page, data.page_size);
  } catch (error) {
    console.error("Error loading products:", error);
    productsGrid.innerHTML = `
      <div class="col-12">
        <div class="alert alert-danger">
          <i class="bi bi-exclamation-triangle"></i> Error loading products. Please try again.
        </div>
      </div>
    `;
  } finally {
    if (loadingSpinner) loadingSpinner.classList.remove("show");
  }
}

// ============================================
// DISPLAY RECOMMENDED PRODUCTS
// ============================================

// # Deprecated 20 Jan

// function displayRecommendedProducts(products) {
//   const productsGrid = document.getElementById("productsGrid");
//   const productCount = document.getElementById("productCount");
//   const pagination = document.getElementById("pagination");

//   if (!productsGrid) return;

//   // Clear existing products
//   productsGrid.innerHTML = "";

//   // Update header to show "Recommended Products"
//   if (productCount) {
//     productCount.innerHTML = `
//       <span class="badge bg-primary me-2">
//         <i class="bi bi-stars"></i> AI Recommended
//       </span>
//       Showing ${products.length} recommended products
//     `;
//   }

//   // Render products using existing createProductCard()
//   products.forEach(product => {
//     const card = createProductCard(product);
//     productsGrid.appendChild(card);
//   });

//   // Hide pagination for recommended view
//   if (pagination) {
//     pagination.innerHTML = "";
//   }

//   // Remove any existing return button first (prevent duplicates)
//   const existingButton = document.getElementById("returnToAllProductsContainer");
//   if (existingButton) {
//     existingButton.remove();
//   }

//   // Add a button to return to regular product listing
//   const returnButton = document.createElement("div");
//   returnButton.id = "returnToAllProductsContainer";
//   returnButton.className = "text-center mt-4 mb-4";
//   returnButton.innerHTML = `
//     <button class="btn btn-outline-secondary btn-lg" id="returnToAllProducts">
//       <i class="bi bi-arrow-left"></i> View All Products
//     </button>
//   `;
//   productsGrid.parentElement.appendChild(returnButton);

//   // Add event listener to return button
//   document.getElementById("returnToAllProducts")?.addEventListener("click", () => {
//     // Remove the return button
//     returnButton.remove();
//     // Reload regular products
//     currentFilters = {};
//     loadProducts(1);
//   });
// }


function createProductCard(product) {

  const col = document.createElement("div");
  col.className = "col-md-4 col-sm-6 mb-4";

  const discountBadge = product.discount_percent
    ? `<span class="discount-badge">${product.discount_percent}% OFF</span>`
    : "";

  const stockBadgeClass =
    {
      "In Stock": "bg-success",
      "Low Stock": "bg-warning",
      "Out of Stock": "bg-danger",
    }[product.stock_status] || "bg-secondary";

  const stockBadge = product.stock_status
    ? `<span class="badge ${stockBadgeClass} stock-badge">${product.stock_status}</span>`
    : "";

  const mrpDisplay =
    product.mrp && product.mrp > product.price
      ? `<span class="mrp">₹${product.mrp.toLocaleString()}</span>`
      : "";

  col.innerHTML = `
    <div class="card product-card h-100">
      <img src="${product.primary_image || "https://via.placeholder.com/400x400?text=No+Image"}" 
           class="card-img-top product-image" 
           alt="${product.title}"
           onerror="this.src='https://via.placeholder.com/400x400?text=No+Image'">
      <div class="card-body d-flex flex-column">
        <div class="mb-2">${stockBadge} ${discountBadge}</div>
        <h6 class="card-title">${product.title}</h6>
        <p class="text-muted small mb-2">
          <i class="bi bi-tag"></i> ${product.brand || "Unknown Brand"}
        </p>
        <div class="mt-auto">
          <div class="price-tag">
            ₹${product.price.toLocaleString()} ${mrpDisplay}
          </div>
          <a href="/product/${product.product_id}" class="btn btn-primary btn-sm w-100 mt-2">
            <i class="bi bi-eye"></i> View Details
          </a>
        </div>
      </div>
    </div>
  `;

  return col;
}

function updatePagination(total, page, pageSize) {
  const pagination = document.getElementById("pagination");
  if (!pagination) return;

  const totalPages = Math.ceil(total / pageSize);

  if (totalPages <= 1) {
    pagination.innerHTML = "";
    return;
  }

  let html = "";

  html += `
    <li class="page-item ${page === 1 ? "disabled" : ""}">
      <a class="page-link" href="#" data-page="${page - 1}">Previous</a>
    </li>
  `;

  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - 2 && i <= page + 2)) {
      html += `
        <li class="page-item ${i === page ? "active" : ""}">
          <a class="page-link" href="#" data-page="${i}">${i}</a>
        </li>
      `;
    } else if (i === page - 3 || i === page + 3) {
      html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
    }
  }

  html += `
    <li class="page-item ${page === totalPages ? "disabled" : ""}">
      <a class="page-link" href="#" data-page="${page + 1}">Next</a>
    </li>
  `;

  pagination.innerHTML = html;

  pagination.querySelectorAll("a.page-link").forEach((link) => {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      const pageNum = parseInt(this.getAttribute("data-page"));
      if (pageNum && pageNum > 0) {
        loadProducts(pageNum);
      }
    });
  });
}

// ✅ FIXED: Properly collect dynamic filters
function applyFilters() {
  currentFilters = {};
  
  // Static filters
  const category = document.getElementById("filterCategory");
  if (category && category.value) currentFilters.category_id = parseInt(category.value);

  const brand = document.getElementById("filterBrand");
  if (brand && brand.value.trim()) currentFilters.brand = brand.value.trim();

  const minPrice = document.getElementById("minPrice");
  if (minPrice && minPrice.value) currentFilters.min_price = parseFloat(minPrice.value);

  const maxPrice = document.getElementById("maxPrice");
  if (maxPrice && maxPrice.value) currentFilters.max_price = parseFloat(maxPrice.value);

  const stock = document.getElementById("filterStock");
  if (stock && stock.value) currentFilters.stock_status = stock.value;

  const sortBy = document.getElementById("sortBy");
  if (sortBy) {
    if (sortBy.value === "price_desc") {
      currentFilters.sort_by = "price";
      currentFilters.sort_order = "desc";
    } else if (sortBy.value === "price") {
      currentFilters.sort_by = "price";
      currentFilters.sort_order = "asc";
    } else if (sortBy.value === "title") {
      currentFilters.sort_by = "title";
      currentFilters.sort_order = "asc";
    }
  }

  // ✅ FIXED: Collect dynamic attribute filters
  const attributeFilters = {};

  // Multi-select checkboxes (NOT toggles)
  document.querySelectorAll('input[type="checkbox"][name^="filter_"]:checked').forEach((input) => {
    // Skip toggle switches
    if (input.parentElement.classList.contains("form-switch")) {
      return;
    }
    
    const attrName = input.name.replace("filter_", "");
    if (!attributeFilters[attrName]) {
      attributeFilters[attrName] = [];
    }
    // ✅ Use original value, not normalized
    attributeFilters[attrName].push(input.value);
  });

  // Range inputs
  document.querySelectorAll('input[type="number"][name^="filter_"]').forEach((input) => {
    const matches = input.name.match(/filter_(.+)_(min|max)/);
    if (matches && input.value) {
      const attrName = matches[1];
      const rangeType = matches[2];

      if (!attributeFilters[attrName]) {
        attributeFilters[attrName] = {};
      }
      attributeFilters[attrName][rangeType] = parseFloat(input.value);
    }
  });

  // Toggle switches
  document.querySelectorAll('.form-switch input[type="checkbox"][name^="filter_"]:checked').forEach((input) => {
    const attrName = input.name.replace("filter_", "");
    attributeFilters[attrName] = true;
  });

  // Clean up empty filters
  Object.keys(attributeFilters).forEach((key) => {
    const val = attributeFilters[key];
    if (
      (Array.isArray(val) && val.length === 0) ||
      (typeof val === "object" && !Array.isArray(val) && Object.keys(val).length === 0)
    ) {
      delete attributeFilters[key];
    }
  });

  // Add to currentFilters as JSON string
  if (Object.keys(attributeFilters).length > 0) {
    currentFilters.filters = JSON.stringify(attributeFilters);
  }

  console.log('Applied filters:', currentFilters);
  console.log('Attribute filters:', attributeFilters);

  currentPage = 1;
  loadProducts(1);
}

function clearFilters() {
  // Clear static filters
  const filterIds = ["filterBrand", "minPrice", "maxPrice", "filterStock", "filterCategory"];

  filterIds.forEach((id) => {
    const element = document.getElementById(id);
    if (element) element.value = "";
  });

  const sortBy = document.getElementById("sortBy");
  if (sortBy) sortBy.value = "product_id";

  // Clear dynamic filters
  clearDynamicFiltersUI();

  currentFilters = {};
  currentPage = 1;
  loadProducts(1);
}

// ============================================
// PRODUCT DETAIL PAGE
// ============================================

async function loadProductDetails(productId) {
  const loadingSpinner = document.getElementById("loadingSpinner");
  const productDetails = document.getElementById("productDetails");
  const errorMessage = document.getElementById("errorMessage");

  try {
    const response = await fetch(`/api/v1/products/${productId}`);

    if (!response.ok) {
      throw new Error("Product not found");
    }

    const product = await response.json();

    const productTitle = document.getElementById("productTitle");
    const productBrand = document.getElementById("productBrand");
    const productType = document.getElementById("productType");
    const productDescription = document.getElementById("productDescription");

    if (productTitle) productTitle.textContent = product.title;
    if (productBrand) productBrand.textContent = product.brand || "Unknown Brand";
    if (productType) productType.textContent = product.product_type || "N/A";

    if (productDescription) {
      productDescription.textContent = product.description || "No description available.";
    }

    const stockBadge = document.getElementById("stockBadge");
    if (stockBadge) {
      const stockClass = {
        "In Stock": "bg-success",
        "Low Stock": "bg-warning",
        "Out of Stock": "bg-danger",
      }[product.stock_status] || "bg-secondary";
      stockBadge.className = `badge ${stockClass}`;
      stockBadge.textContent = product.stock_status || "Unknown";
    }

    const priceDisplay = document.getElementById("priceDisplay");
    if (priceDisplay) priceDisplay.textContent = `₹${product.price.toLocaleString()}`;

    const mrpDisplay = document.getElementById("mrpDisplay");
    if (mrpDisplay) {
      if (product.mrp && product.mrp > product.price) {
        mrpDisplay.textContent = `MRP: ₹${product.mrp.toLocaleString()}`;
        mrpDisplay.style.display = "block";
      } else {
        mrpDisplay.style.display = "none";
      }
    }

    const discountBadge = document.getElementById("discountBadge");
    if (discountBadge) {
      if (product.discount_percent) {
        discountBadge.innerHTML = `<span class="badge bg-danger">${product.discount_percent}% OFF</span>`;
      } else {
        discountBadge.innerHTML = "";
      }
    }

    const mainImage = document.getElementById("mainImage");
    const thumbnailContainer = document.getElementById("thumbnailContainer");

    if (product.images && product.images.length > 0) {
      if (mainImage) {
        mainImage.src = product.images[0].image_url;
        mainImage.alt = product.title;
      }

      if (thumbnailContainer) {
        product.images.forEach((image, index) => {
          const thumbnail = document.createElement("img");
          thumbnail.src = image.image_url;
          thumbnail.className = "product-thumbnail" + (index === 0 ? " active" : "");
          thumbnail.onclick = () => {
            if (mainImage) mainImage.src = image.image_url;
            document.querySelectorAll(".product-thumbnail").forEach((t) => t.classList.remove("active"));
            thumbnail.classList.add("active");
          };
          thumbnail.onerror = function () {
            this.src = "https://via.placeholder.com/100x100?text=Image";
          };
          thumbnailContainer.appendChild(thumbnail);
        });
      }
    } else {
      if (mainImage) mainImage.src = "https://via.placeholder.com/500x500?text=No+Image";
    }

    const attributesTable = document.getElementById("attributesTable");

    if (attributesTable) {
      attributesTable.innerHTML = "";

      if (product.attributes && product.attributes.length > 0) {
        product.attributes.forEach((attr) => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td><strong>${formatAttributeName(attr.attribute_name)}</strong></td>
            <td>${attr.value ?? "N/A"}</td>
          `;
          attributesTable.appendChild(row);
        });
      } else {
        attributesTable.innerHTML =
          '<tr><td colspan="2" class="text-muted">No attributes available</td></tr>';
      }
    }


    const addToCartBtn = document.getElementById("addToCartBtn");
    if (addToCartBtn) {
      if (product.stock_status === "Out of Stock") {
        addToCartBtn.disabled = true;
        addToCartBtn.textContent = "Out of Stock";
      }
    }

    if (loadingSpinner) loadingSpinner.style.display = "none";
    if (productDetails) productDetails.style.display = "block";
  } catch (error) {
    console.error("Error loading product:", error);
    if (loadingSpinner) loadingSpinner.style.display = "none";
    if (errorMessage) {
      errorMessage.style.display = "block";
      const errorText = document.getElementById("errorText");
      if (errorText) errorText.textContent = error.message || "Failed to load product details";
    }
  }
}

function formatAttributeName(name) {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// ============================================
// INITIALIZATION
// ============================================


document.addEventListener("DOMContentLoaded", async function () {
  // ============================
  // SESSION INITIALIZATION
  // ============================
  // Try to restore existing session from localStorage
  const sessionRestored = await restoreSession();
  
  // If no session restored, create new one
  if (!sessionRestored) {
    await createNewSession();
  }
  
  // ============================
  // CHAT INITIALIZATION
  // ============================
  const chatToggleBtn = document.getElementById("chatToggleBtn");
  const closeChatBtn = document.getElementById("closeChatBtn");
  const chatSendBtn = document.getElementById("chatSendBtn");
  const chatInput = document.getElementById("chatInput");

  if (chatToggleBtn) chatToggleBtn.addEventListener("click", toggleChat);
  if (closeChatBtn) closeChatBtn.addEventListener("click", toggleChat);
  if (chatSendBtn) chatSendBtn.addEventListener("click", sendChatMessage);
  if (chatInput) chatInput.addEventListener("keypress", handleChatKeyPress);

  // Initialize session UI for conversational agent
  initializeSessionUI();

  // ============================
  // PRODUCT LISTING PAGE
  // ============================
  const productsGrid = document.getElementById("productsGrid");
  if (productsGrid) {
    try {
      // 1️⃣ Load categories FIRST
      await loadCategories();

      // 2️⃣ Read selected category (auto-selected or user-selected)
      const categorySelect = document.getElementById("filterCategory");
      const categoryId = categorySelect?.value
        ? parseInt(categorySelect.value)
        : null;

      // 3️⃣ Load filters ONLY if category exists
      if (categoryId) {
        await loadDynamicFilters(categoryId);
      }

      // 4️⃣ Load products
      loadProducts(1);

      // ============================
      // FILTER BUTTONS
      // ============================
      const applyFiltersBtn = document.getElementById("applyFiltersBtn");
      const clearFiltersBtn = document.getElementById("clearFiltersBtn");

      if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener("click", applyFilters);
      }

      if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener("click", clearFilters);
      }

      // ============================
      // CATEGORY CHANGE HANDLER
      // ============================
      if (categorySelect) {
        categorySelect.addEventListener("change", async function () {
          const newCategoryId = this.value ? parseInt(this.value) : null;

          // Reset state
          currentFilters = {};
          clearDynamicFiltersUI();

          if (newCategoryId) {
            await loadDynamicFilters(newCategoryId);
          }

          loadProducts(1);
        });
      }
    } catch (err) {
      console.error("Initialization error:", err);
    }
  }

  // ============================
  // PRODUCT DETAIL PAGE
  // ============================
  const productContainer = document.getElementById("productContainer");
  if (productContainer) {
    const pathParts = window.location.pathname.split("/");
    const productId = pathParts[pathParts.length - 1];

    if (productId && productId !== "product" && !productId.endsWith(".html")) {
      await loadProductDetails(productId);
    }
  }

  // ============================
  // ENTER KEY = APPLY FILTERS
  // ============================
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target.closest(".filter-group")) {
      applyFilters();
    }
  });
});
