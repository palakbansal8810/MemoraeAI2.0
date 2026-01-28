#!/usr/bin/env python3
"""
List Items Diagnostic Script
Check if list items are properly stored and can be retrieved
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db, List, ListItem, User

def check_all_lists():
    """Check all lists and their items"""
    print("=" * 60)
    print("Checking Lists and Items in Database")
    print("=" * 60)
    
    db = get_db()
    try:
        # Get all lists
        lists = db.query(List).all()
        
        if not lists:
            print("\n❌ No lists found in database")
            return
        
        print(f"\n📊 Found {len(lists)} lists\n")
        
        for list_obj in lists:
            user = db.query(User).filter(User.id == list_obj.user_id).first()
            
            print(f"\n{'='*50}")
            print(f"List ID: {list_obj.id}")
            print(f"List Name: '{list_obj.name}'")
            print(f"User: {user.first_name if user else 'Unknown'} (ID: {user.telegram_id if user else 'N/A'})")
            print(f"Created: {list_obj.created_at}")
            
            # Get items for this list
            items = db.query(ListItem).filter(ListItem.list_id == list_obj.id).all()
            
            print(f"\nItems in this list: {len(items)}")
            
            if items:
                print("\nItems:")
                for i, item in enumerate(items, 1):
                    status = "✅" if item.completed else "⭕"
                    print(f"  {i}. {status} {item.content} (ID: {item.id})")
            else:
                print("  ❌ No items found for this list!")
        
        print(f"\n{'='*60}")
        
        # Summary
        total_items = db.query(ListItem).count()
        print(f"SUMMARY:")
        print(f"Total lists: {len(lists)}")
        print(f"Total items across all lists: {total_items}")
        
        # Check for orphaned items (items without a valid list)
        orphaned = db.query(ListItem).filter(
            ~ListItem.list_id.in_(db.query(List.id))
        ).count()
        
        if orphaned > 0:
            print(f"⚠️  Orphaned items (no valid list): {orphaned}")
        
    except Exception as e:
        print(f"\n❌ Error checking lists: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def check_specific_list(list_name: str):
    """Check a specific list by name"""
    print(f"\n{'='*60}")
    print(f"Checking '{list_name}' list")
    print("=" * 60)
    
    db = get_db()
    try:
        # Find list by name (case-insensitive)
        list_obj = db.query(List).filter(
            List.name.ilike(f"%{list_name}%")
        ).first()
        
        if not list_obj:
            print(f"\n❌ No list found matching '{list_name}'")
            
            # Show available lists
            all_lists = db.query(List).all()
            if all_lists:
                print("\nAvailable lists:")
                for lst in all_lists:
                    print(f"  - {lst.name}")
            return
        
        print(f"\n✅ Found list: '{list_obj.name}' (ID: {list_obj.id})")
        
        # Get items
        items = db.query(ListItem).filter(ListItem.list_id == list_obj.id).all()
        
        print(f"\nItems in this list: {len(items)}")
        
        if items:
            print("\nDetailed items:")
            for item in items:
                print(f"\n  Item ID: {item.id}")
                print(f"  Content: '{item.content}'")
                print(f"  Completed: {item.completed}")
                print(f"  Created: {item.created_at}")
        else:
            print("\n❌ This list has NO ITEMS!")
            print("\nPossible reasons:")
            print("1. Items were never added to database")
            print("2. Items are being added to a different list ID")
            print("3. Items were deleted")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def test_add_item_to_list():
    """Test adding an item to a list"""
    print(f"\n{'='*60}")
    print("Testing Adding Item to List")
    print("=" * 60)
    
    db = get_db()
    try:
        # Find shopping list
        shopping_list = db.query(List).filter(
            List.name.ilike("%shopping%")
        ).first()
        
        if not shopping_list:
            print("\n❌ Shopping list not found, creating one...")
            
            # Get or create test user
            user = db.query(User).filter(User.telegram_id == 999999999).first()
            if not user:
                user = User(
                    telegram_id=999999999,
                    username="test_user",
                    first_name="Test User"
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            shopping_list = List(
                user_id=user.id,
                name="shopping list"
            )
            db.add(shopping_list)
            db.commit()
            db.refresh(shopping_list)
            print(f"✅ Created shopping list (ID: {shopping_list.id})")
        
        print(f"\nAdding test item to list '{shopping_list.name}' (ID: {shopping_list.id})")
        
        # Add test item
        test_item = ListItem(
            list_id=shopping_list.id,
            content="TEST ITEM - Added by diagnostic script",
            completed=False
        )
        
        db.add(test_item)
        db.commit()
        db.refresh(test_item)
        
        print(f"✅ Test item added! (ID: {test_item.id})")
        
        # Verify by reading back
        verify = db.query(ListItem).filter(ListItem.id == test_item.id).first()
        
        if verify:
            print(f"✅ Verified item in database:")
            print(f"   Content: '{verify.content}'")
            print(f"   List ID: {verify.list_id}")
            print(f"   Completed: {verify.completed}")
        else:
            print(f"❌ Could not verify item!")
        
        # Count items in list
        item_count = db.query(ListItem).filter(
            ListItem.list_id == shopping_list.id
        ).count()
        
        print(f"\nTotal items in {shopping_list.name}: {item_count}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    check_all_lists()
    check_specific_list("shopping")
    test_add_item_to_list()
    
    print("\n" + "=" * 60)
    print("Next: Check if the problem is in retrieval or storage")
    print("=" * 60)