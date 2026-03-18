#!/usr/bin/env python3
"""
Code Examples Generator

Provides framework-specific code examples for various tech stacks
to use as references in LLM prompts.
"""


def get_crud_example(backend_framework: str) -> str:
    """Return framework-specific CRUD API example"""
    
    examples = {
        "fastapi": """
# FastAPI CRUD Example (COMPLETE - Use this as reference)
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/", response_model=List[schemas.Item])
async def list_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    \"\"\"Retrieve paginated list of items\"\"\"
    try:
        items = db.query(models.Item).offset(skip).limit(limit).all()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{item_id}", response_model=schemas.Item)
async def get_item(item_id: int, db: Session = Depends(get_db)):
    \"\"\"Get single item by ID\"\"\"
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.post("/", response_model=schemas.Item, status_code=status.HTTP_201_CREATED)
async def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    \"\"\"Create new item\"\"\"
    try:
        db_item = models.Item(**item.dict())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{item_id}", response_model=schemas.Item)
async def update_item(
    item_id: int,
    item: schemas.ItemUpdate,
    db: Session = Depends(get_db)
):
    \"\"\"Update existing item\"\"\"
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    for key, value in item.dict(exclude_unset=True).items():
        setattr(db_item, key, value)
    
    try:
        db.commit()
        db.refresh(db_item)
        return db_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, db: Session = Depends(get_db)):
    \"\"\"Delete item\"\"\"
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    try:
        db.delete(db_item)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
""",

        "flask": """
# Flask CRUD Example (COMPLETE - Use this as reference)
from flask import Blueprint, request, jsonify
from models import db, Item
from schemas import ItemSchema, validate_item
from sqlalchemy.exc import SQLAlchemyError

bp = Blueprint('items', __name__, url_prefix='/items')
item_schema = ItemSchema()
items_schema = ItemSchema(many=True)

@bp.route('/', methods=['GET'])
def list_items():
    \"\"\"Retrieve paginated list of items\"\"\"
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)
    
    try:
        items = Item.query.offset(skip).limit(limit).all()
        return jsonify(items_schema.dump(items)), 200
    except SQLAlchemyError as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/<int:item_id>', methods=['GET'])
def get_item(item_id):
    \"\"\"Get single item by ID\"\"\"
    item = Item.query.get(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(item_schema.dump(item)), 200

@bp.route('/', methods=['POST'])
def create_item():
    \"\"\"Create new item\"\"\"
    try:
        data = item_schema.load(request.json)
        item = Item(**data)
        db.session.add(item)
        db.session.commit()
        return jsonify(item_schema.dump(item)), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    \"\"\"Update existing item\"\"\"
    item = Item.query.get(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    
    try:
        data = item_schema.load(request.json, partial=True)
        for key, value in data.items():
            setattr(item, key, value)
        db.session.commit()
        return jsonify(item_schema.dump(item)), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    \"\"\"Delete item\"\"\"
    item = Item.query.get(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404
    
    try:
        db.session.delete(item)
        db.session.commit()
        return '', 204
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
""",

        "express": """
// Express.js CRUD Example (COMPLETE - Use this as reference)
const express = require('express');
const router = express.Router();
const { Item } = require('../models');
const { validateItem } = require('../validators');

router.get('/items', async (req, res) => {
    /**
     * Retrieve paginated list of items
     */
    try {
        const { skip = 0, limit = 100 } = req.query;
        const items = await Item.findAll({
            offset: parseInt(skip),
            limit: parseInt(limit)
        });
        res.json(items);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

router.get('/items/:id', async (req, res) => {
    /**
     * Get single item by ID
     */
    try {
        const item = await Item.findByPk(req.params.id);
        if (!item) {
            return res.status(404).json({ error: 'Item not found' });
        }
        res.json(item);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

router.post('/items', validateItem, async (req, res) => {
    /**
     * Create new item
     */
    try {
        const item = await Item.create(req.body);
        res.status(201).json(item);
    } catch (error) {
        res.status(400).json({ error: error.message });
    }
});

router.put('/items/:id', validateItem, async (req, res) => {
    /**
     * Update existing item
     */
    try {
        const item = await Item.findByPk(req.params.id);
        if (!item) {
            return res.status(404).json({ error: 'Item not found' });
        }
        await item.update(req.body);
        res.json(item);
    } catch (error) {
        res.status(400).json({ error: error.message });
    }
});

router.delete('/items/:id', async (req, res) => {
    /**
     * Delete item
     */
    try {
        const item = await Item.findByPk(req.params.id);
        if (!item) {
            return res.status(404).json({ error: 'Item not found' });
        }
        await item.destroy();
        res.status(204).send();
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;
""",

        "django": """
# Django REST Framework CRUD Example (COMPLETE - Use this as reference)
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Item
from .serializers import ItemSerializer

class ItemViewSet(viewsets.ModelViewSet):
    \"\"\"
    ViewSet for Item CRUD operations
    \"\"\"
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    
    def list(self, request):
        \"\"\"Retrieve paginated list of items\"\"\"
        skip = int(request.query_params.get('skip', 0))
        limit = int(request.query_params.get('limit', 100))
        
        items = self.queryset[skip:skip+limit]
        serializer = self.serializer_class(items, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        \"\"\"Get single item by ID\"\"\"
        try:
            item = self.queryset.get(pk=pk)
            serializer = self.serializer_class(item)
            return Response(serializer.data)
        except Item.DoesNotExist:
            return Response(
                {"error": "Item not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def create(self, request):
        \"\"\"Create new item\"\"\"
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, pk=None):
        \"\"\"Update existing item\"\"\"
        try:
            item = self.queryset.get(pk=pk)
            serializer = self.serializer_class(item, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Item.DoesNotExist:
            return Response(
                {"error": "Item not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def destroy(self, request, pk=None):
        \"\"\"Delete item\"\"\"
        try:
            item = self.queryset.get(pk=pk)
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Item.DoesNotExist:
            return Response(
                {"error": "Item not found"},
                status=status.HTTP_404_NOT_FOUND
            )
"""
    }
    
    return examples.get(backend_framework, """
# NO FRAMEWORK DETECTED - Use these general principles:
# 1. Complete CRUD operations (GET, POST, PUT, DELETE)
# 2. Error handling for all database operations
# 3. Input validation before processing
# 4. Proper HTTP status codes (200, 201, 204, 400, 404, 500)
# 5. Pagination support for list endpoints
# 6. Transaction management (rollback on error)
""")


def get_frontend_example(frontend_framework: str) -> str:
    """Return framework-specific frontend component example"""
    
    examples = {
        "react": """
// React Project Structure (COMPLETE - Use this as reference)
// index.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>React App</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
</body>
</html>

// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// src/App.jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const App = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    // ... rest of component logic ...
};
export default App;
""",

        "vue": """
<!-- Vue Component Example (COMPLETE - Use this as reference) -->
<template>
  <div class="item-list">
    <h2>Items</h2>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error" class="error">Error: {{ error }}</div>
    <div v-else>
      <form @submit.prevent="handleSubmit">
        <input
          v-model="newItem.name"
          type="text"
          placeholder="Name"
          required
        />
        <input
          v-model="newItem.description"
          type="text"
          placeholder="Description"
        />
        <button type="submit">Add Item</button>
      </form>
      <ul>
        <li v-for="item in items" :key="item.id">
          <h3>{{ item.name }}</h3>
          <p>{{ item.description }}</p>
          <button @click="handleDelete(item.id)">Delete</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'ItemList',
  data() {
    return {
      items: [],
      loading: true,
      error: null,
      newItem: {
        name: '',
        description: ''
      }
    };
  },
  mounted() {
    this.fetchItems();
  },
  methods: {
    async fetchItems() {
      try {
        const response = await axios.get('/api/items');
        this.items = response.data;
        this.loading = false;
      } catch (err) {
        this.error = err.message;
        this.loading = false;
      }
    },
    async handleSubmit() {
      try {
        await axios.post('/api/items', this.newItem);
        this.newItem = { name: '', description: '' };
        this.fetchItems();
      } catch (err) {
        this.error = err.message;
      }
    },
    async handleDelete(id) {
      try {
        await axios.delete(`/api/items/${id}`);
        this.fetchItems();
      } catch (err) {
        this.error = err.message;
      }
    }
  }
};
</script>

<style scoped>
.error {
  color: red;
  padding: 10px;
  margin: 10px 0;
}
</style>
""",

        "vanilla": """
// Vanilla JavaScript Example (COMPLETE - Use this as reference)
class ItemManager {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
        this.items = [];
        this.init();
    }

    init() {
        this.renderForm();
        this.fetchItems();
    }

    async fetchItems() {
        const container = document.getElementById('items-container');
        container.innerHTML = '<p>Loading...</p>';

        try {
            const response = await fetch(`${this.apiBaseUrl}/items`);
            if (!response.ok) throw new Error('Failed to fetch items');
            this.items = await response.json();
            this.renderItems();
        } catch (error) {
            container.innerHTML = `<p class="error">Error: ${error.message}</p>`;
        }
    }

    renderForm() {
        const formHtml = `
            <form id="item-form">
                <input type="text" id="item-name" placeholder="Name" required />
                <input type="text" id="item-description" placeholder="Description" />
                <button type="submit">Add Item</button>
            </form>
        `;
        document.getElementById('form-container').innerHTML = formHtml;

        document.getElementById('item-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createItem();
        });
    }

    renderItems() {
        const container = document.getElementById('items-container');
        
        if (this.items.length === 0) {
            container.innerHTML = '<p>No items found</p>';
            return;
        }

        const itemsHtml = this.items.map(item => `
            <div class="item" data-id="${item.id}">
                <h3>${this.escapeHtml(item.name)}</h3>
                <p>${this.escapeHtml(item.description || '')}</p>
                <button onclick="itemManager.deleteItem(${item.id})">Delete</button>
            </div>
        `).join('');

        container.innerHTML = itemsHtml;
    }

    async createItem() {
        const name = document.getElementById('item-name').value;
        const description = document.getElementById('item-description').value;

        try {
            const response = await fetch(`${this.apiBaseUrl}/items`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description })
            });

            if (!response.ok) throw new Error('Failed to create item');

            document.getElementById('item-form').reset();
            this.fetchItems();
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }

    async deleteItem(id) {
        if (!confirm('Delete this item?')) return;

        try {
            const response = await fetch(`${this.apiBaseUrl}/items/${id}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to delete item');
            this.fetchItems();
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on page load
const itemManager = new ItemManager('/api');
"""
    }
    
    return examples.get(frontend_framework, """
// NO FRAMEWORK DETECTED - Use these general principles:
// 1. Proper error handling for API calls
// 2. Loading states during async operations
// 3. Input validation before submission
// 4. Escape user input to prevent XSS
// 5. Accessible HTML (ARIA labels, semantic elements)
// 6. Responsive CSS (mobile-first approach)
""")
