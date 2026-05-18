"""
Whitelist Service - Business logic for whitelist operations
- Clean and simple
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from models.whitelist_model import WhitelistModel

# Import time utilities - vietnam ONLY
from time_utils import (
    now_iso,
    now_vietnam,
    parse_agent_timestamp,
    to_vietnam,
)

logger = logging.getLogger(__name__)

class WhitelistService:
    """Service class for whitelist business logic - vietnam ONLY"""
    
    def __init__(self, whitelist_model: WhitelistModel, agent_model, group_model, socketio=None,
                 policy_service=None, profile_service=None):
        """Initialize WhitelistService with model and socketio"""
        self.model = whitelist_model
        self.agent_model = agent_model
        self.group_model = group_model
        self.socketio = socketio
        self.policy_service = policy_service
        self.profile_service = profile_service
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.logger.info("WhitelistService initialized with vietnam timezone support")
    
    def get_all_entries(self, filters: Dict = None) -> Dict:
        """Get all whitelist entries with optional filtering - vietnam ONLY"""
        query = {}
        if filters:
            query = self.model.build_query_from_filters(filters)
        
        entries = self.model.find_all_entries(query)
        
        # Format entries for response
        formatted_entries = []
        for entry in entries:
            # FIX: Ensure all required fields are present
            formatted_entry = {
                "_id": entry.get("_id"),  # Keep _id for frontend
                "id": entry.get("_id"),   # Also add id for compatibility
                "type": entry.get("type", "domain"),
                "value": entry.get("value", ""),  # Always use 'value'
                "category": entry.get("category", "uncategorized"),
                "priority": entry.get("priority", "normal"),
                "added_by": entry.get("added_by", "unknown"),
                "is_active": entry.get("is_active", True),
                "scope": entry.get("scope", "global"),
                "added_date": None
            }
            
            # FIX: Proper date handling
            if entry.get("added_date"):
                try:
                    if hasattr(entry["added_date"], 'isoformat'):
                        formatted_entry["added_date"] = entry["added_date"].isoformat()
                    else:
                        formatted_entry["added_date"] = str(entry["added_date"])
                except Exception:
                    formatted_entry["added_date"] = None
            
            # Add optional fields if they exist
            if entry.get("notes"):
                formatted_entry["notes"] = entry.get("notes")
            if entry.get("group_id"):
                formatted_entry["group_id"] = entry.get("group_id")
            if entry.get("group_name"):
                formatted_entry["group_name"] = entry.get("group_name")
            
            formatted_entries.append(formatted_entry)
        
        return {
            "domains": formatted_entries,
            "success": True,
            "server_time": now_iso()
        }
    
    def add_entry(self, entry_data: Dict, client_ip: str) -> Dict:
        """Add new entry to whitelist - vietnam ONLY"""
        entry_type = entry_data.get("type", "domain")
        value = entry_data.get("value", "").strip().lower()
        
        if not value:
            raise ValueError("Value is required")
        
        # Validate entry using model
        validation_result = self.model.validate_entry_value(entry_type, value)
        if not validation_result["valid"]:
            raise ValueError(validation_result["message"])
        
        # Check for duplicates in global whitelist (both active and inactive)
        existing = self.model.find_entry_by_value(value, active_only=False)
        if existing and existing.get("scope", "global") == "global":
            if existing.get("is_active", True):
                raise ValueError("Entry already exists in global whitelist")
            else:
                # Re-activate the existing inactive entry instead of creating duplicate
                self.model.collection.update_one(
                    {"_id": ObjectId(existing["_id"])},
                    {"$set": {"is_active": True, "updated_at": now_vietnam()}}
                )
                self.model.bump_global_version()
                return self.model.find_entry_by_id(existing["_id"])
        
        # Use vietnam time for timestamps
        current_time = now_vietnam()
        logger.info(f"Adding entry with vietnam timestamp: {current_time}")
        
        # Create processed entry.
        # Frontend may send the categorical label as either `category` or
        # `description` (legacy form field) — accept both.
        category_value = (
            entry_data.get("category")
            or entry_data.get("description")
            or "uncategorized"
        )
        processed_entry = {
            "type": entry_type,
            "value": value,
            "category": category_value,
            "priority": entry_data.get("priority", "normal"),
            "added_by": client_ip,
            "added_date": current_time,
            "is_active": True
        }

        # Add optional fields if specified
        if entry_data.get("notes"):
            processed_entry["notes"] = entry_data.get("notes")
        
        if entry_data.get("expiry_date"):
            try:
                # Parse expiry date using vietnam parsing
                expiry_vietnam = parse_agent_timestamp(entry_data["expiry_date"])
                processed_entry["expiry_date"] = expiry_vietnam
                
            except Exception as e:
                logger.warning(f"Invalid expiry date format: {e}")
                raise ValueError("Invalid expiry date format")
                
        elif entry_data.get("is_temporary"):
            processed_entry["is_temporary"] = True
            processed_entry["expiry_date"] = current_time + timedelta(hours=24)
        
        if entry_data.get("max_requests_per_hour"):
            try:
                processed_entry["max_requests_per_hour"] = int(entry_data["max_requests_per_hour"])
            except (ValueError, TypeError):
                pass
        
        if entry_type == "domain" and entry_data.get("dns_config"):
            dns_config = entry_data["dns_config"]
            if dns_config.get("verify"):
                dns_result = self.model.verify_dns(value)
                if not dns_result["valid"]:
                    raise ValueError(f"DNS verification failed: {dns_result['message']}")
                processed_entry["dns_info"] = dns_result["info"]
            processed_entry["dns_config"] = dns_config
        
        # Insert entry using model
        try:
            entry_id = self.model.insert_entry(processed_entry)
            logger.info(f"Successfully inserted entry with ID: {entry_id}")
        except Exception as e:
            logger.error(f"Failed to insert entry: {e}")
            raise
        
        # Broadcast notification via SocketIO - vietnam only
        if self.socketio:
            self.socketio.emit("whitelist_added", {
                "type": entry_type,
                "value": value,
                "category": processed_entry["category"],
                "added_by": client_ip,
                "timestamp": now_iso()  # vietnam ISO
            })
        
        return {
            "id": entry_id,
            "message": f"{entry_type.capitalize()} added to whitelist",
            "timestamp": now_iso(),  # vietnam ISO
            "server_time": now_iso()  # vietnam ISO
        }
    
    def test_entry(self, entry_data: Dict) -> Dict:
        """Test an entry before adding it - vietnam ONLY"""
        try:
            entry_type = entry_data.get("type", "domain")
            value = entry_data.get("value", "").strip().lower()
            
            if not value:
                return {"valid": False, "message": "Value is required"}
            
            # Validate entry using model
            validation_result = self.model.validate_entry_value(entry_type, value)
            
            if not validation_result["valid"]:
                return validation_result
            
            # Check for duplicates
            existing = self.model.find_entry_by_value(value)
            if existing:
                return {"valid": False, "message": "Entry already exists"}
            
            # Additional tests based on type
            if entry_type == "domain":
                try:
                    # Test DNS resolution
                    import socket
                    socket.getaddrinfo(value, None, socket.AF_INET)
                    dns_info = f"DNS resolution successful"
                except Exception as e:
                    dns_info = f"DNS resolution failed: {str(e)}"
                
                return {
                    "valid": True,
                    "message": "Entry is valid",
                    "dns_info": dns_info,
                    "server_time": now_iso()  # vietnam ISO
                }
            
            return {
                "valid": True, 
                "message": "Entry is valid",
                "server_time": now_iso()  # vietnam ISO
            }
            
        except Exception as e:
            self.logger.error(f"Error testing entry: {e}")
            return {
                "valid": False, 
                "message": f"Test failed: {str(e)}",
                "server_time": now_iso()  # vietnam ISO
            }
    
    def test_dns(self, domain: str) -> Dict:
        """Test DNS resolution for a domain - vietnam ONLY"""
        try:
            if not domain:
                return {
                    "valid": False, 
                    "message": "Domain is required",
                    "server_time": now_iso()  # vietnam ISO
                }
            
            domain = domain.strip().lower()
            
            # Validate domain format first
            validation_result = self.model.validate_entry_value("domain", domain)
            if not validation_result["valid"]:
                return {
                    **validation_result,
                    "server_time": now_iso()  # vietnam ISO
                }
            
            # Test DNS resolution
            import socket
            try:
                results = socket.getaddrinfo(domain, None, socket.AF_INET)
                ips = []
                for result in results:
                    ip = result[4][0]
                    if ip not in ips:
                        ips.append(ip)
                
                return {
                    "valid": True,
                    "message": f"DNS resolution successful",
                    "domain": domain,
                    "ips": ips,
                    "count": len(ips),
                    "server_time": now_iso()  # vietnam ISO
                }
                
            except Exception as e:
                return {
                    "valid": False,
                    "message": f"DNS resolution failed: {str(e)}",
                    "domain": domain,
                    "server_time": now_iso()  # vietnam ISO
                }
                
        except Exception as e:
            self.logger.error(f"Error testing DNS: {e}")
            return {
                "valid": False, 
                "message": f"DNS test failed: {str(e)}",
                "server_time": now_iso()  # vietnam ISO
            }
    
    def _get_detailed_changes(self, since_dt: datetime) -> Dict:
        """Get detailed changes since specified time - vietnam ONLY"""
        try:
            changes = {
                "added": [],
                "removed": [],
                "modified": [],
                "active_domains": []
            }
            
            # Get ALL currently active domains
            all_active_query = {"is_active": True}
            all_active_entries = list(self.model.collection.find(all_active_query))
            changes["active_domains"] = [entry.get("value") for entry in all_active_entries]
            
            #  ADD: Debug logging
            self.logger.debug(f"Total active domains in DB: {len(changes['active_domains'])}")
            self.logger.debug(f"Active domains: {changes['active_domains']}")
            
            # Get newly added entries
            added_query = {
                "is_active": True,
                "added_date": {"$gte": since_dt}
            }
            added_entries = list(self.model.collection.find(added_query))
            
            #  ADD: Debug logging
            self.logger.debug(f"Newly added since {since_dt}: {len(added_entries)}")
            
            for entry in added_entries:
                changes["added"].append({
                    "value": entry.get("value"),
                    "type": entry.get("type", "domain"),
                    "category": entry.get("category", "uncategorized"),
                    "added_date": entry.get("added_date").isoformat() if entry.get("added_date") else None,
                    "added_by": entry.get("added_by", "system")
                })
            
            # For hard deletes, we rely on active_domains comparison in agent
            # For soft deletes (is_active = False)
            deactivated_query = {
                "is_active": False,
                "updated_at": {"$gte": since_dt}
            }
            deactivated_entries = list(self.model.collection.find(deactivated_query))
            
            #  ADD: Debug logging
            self.logger.debug(f"Deactivated since {since_dt}: {len(deactivated_entries)}")
            
            for entry in deactivated_entries:
                changes["removed"].append({
                    "value": entry.get("value"),
                    "type": entry.get("type", "domain"),
                    "category": entry.get("category", "uncategorized"),
                    "removed_date": entry.get("updated_at").isoformat() if entry.get("updated_at") else None,
                    "reason": "deactivated"
                })
            
            self.logger.info(f"Change details: {len(changes['added'])} added, "
                            f"{len(changes['removed'])} removed, "
                            f"{len(changes['active_domains'])} total active")
            
            return changes
            
        except Exception as e:
            self.logger.error(f"Error getting detailed changes: {e}")
            return {"added": [], "removed": [], "modified": [], "active_domains": []}
    
    def _normalize_group_entries(self, group, include_inactive: bool = True) -> List[Dict]:
        """Normalize entries from group.whitelist into a list of dicts.

        Args:
            include_inactive: when False, entries with `is_active=False` are
                skipped (used for agent sync). UI listings keep the default
                True so admins can see & re-activate disabled items.
        """
        entries = []
        group_id = str(group.get("_id")) if group else None
        group_name = group.get("name") if group else None

        for entry in group.get("whitelist", []):
            if not entry:
                continue
            if isinstance(entry, dict):
                value = entry.get("value")
                entry_type = entry.get("type", "domain")
                priority = entry.get("priority", "normal")
                category = entry.get("category", "uncategorized")
                is_active = entry.get("is_active", True)
            else:
                value = entry
                entry_type = "domain"
                priority = "normal"
                category = "uncategorized"
                is_active = True

            if not include_inactive and not is_active:
                continue

            # Create a pseudo-ID for group items so they can be selected/manipulated on frontend
            # format: group::<group_id>::<type>::<value>
            # Using :: as separator to avoid conflicts with | in URLs
            pseudo_id = f"group::{group_id}::{entry_type}::{value}"

            entries.append({
                "_id": pseudo_id,
                "id": pseudo_id,
                "value": value,
                "type": entry_type,
                "priority": priority,
                "category": category,
                "is_active": is_active,
                "scope": "group",
                "group_id": group_id,
                "group_name": group_name,
            })
        return entries

    def _merge_whitelists(self, global_entries: List[Dict], group_entries: List[Dict]) -> List[Dict]:
        """Merge global and group whitelists.
        When the same type:value exists in both scopes, group entry wins
        (more specific scope takes priority) with consistent _id and scope.
        """
        merged = {}
        for entry in global_entries + group_entries:
            key = f"{entry.get('type', 'domain')}:{entry.get('value')}"
            existing = merged.get(key)

            if existing:
                # Group scope wins over global (more specific)
                incoming_scope = entry.get("scope", "global")
                existing_scope = existing.get("scope", "global")
                if incoming_scope == "group" or existing_scope != "group":
                    # Incoming is group or existing is not group → use incoming
                    entry_copy = {**entry}
                    # Use higher priority if different
                    if existing.get("priority") == "high" and entry_copy.get("priority") != "high":
                        entry_copy["priority"] = "high"
                    merged[key] = entry_copy
                else:
                    # Existing is group, incoming is global → keep existing, merge optional fields
                    if entry.get("priority") == "high":
                        existing["priority"] = "high"
            else:
                merged[key] = {**entry}

        return list(merged.values())

    def get_scoped_whitelist(self, agent_id: Optional[str] = None, group_id: Optional[str] = None) -> Dict:
        """Return global and group whitelist entries with version metadata."""
        try:
            target_group_id = group_id
            agent = None

            if agent_id:
                agent = self.agent_model.find_by_agent_id(agent_id)
                if not agent:
                    raise ValueError("Agent not found")
                target_group_id = target_group_id or agent.get("group_id")

            group = self.group_model.find_by_id(target_group_id) if target_group_id else None
            if not group:
                group = self.group_model.ensure_pending_group()
                target_group_id = str(group.get("_id"))
                if agent and not agent.get("group_id"):
                    self.agent_model.update_agent(agent_id, {"group_id": target_group_id, "status": agent.get("status", "pending")})

            global_entries = self.model.get_entries_for_sync(scope="global")
            for entry in global_entries:
                entry.setdefault("scope", "global")

            group_entries = self._normalize_group_entries(group)
            combined = self._merge_whitelists(global_entries, group_entries)

            return {
                "success": True,
                "global": global_entries,
                "group": group_entries,
                "merged": combined,
                "global_version": self.model.get_global_version(),
                "group_version": group.get("whitelist_version", 1),
                "group_id": str(group.get("_id")),
                "group_name": group.get("name"),
                "timestamp": now_iso(),
            }
        except Exception as exc:
            self.logger.error(f"Error getting scoped whitelist: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "global": [],
                "group": [],
                "merged": [],
                "timestamp": now_iso(),
            }

    def get_agent_sync_data(self, since_datetime=None, agent_id: str = None,
                            global_version: Optional[int] = None, group_version: Optional[int] = None,
                            agent_policy_mode: str = "none") -> Dict:
        """Get whitelist data for agent synchronization with group awareness.
        Note: since_datetime is kept for API compatibility but ignored (always full sync)."""
        try:
            if not agent_id:
                raise ValueError("agent_id is required for sync")

            agent = self.agent_model.find_by_agent_id(agent_id)
            if not agent:
                raise ValueError("Agent not found")

            group_id = agent.get("group_id")
            group = self.group_model.find_by_id(group_id) if group_id else None
            if not group:
                group = self.group_model.ensure_pending_group()
                group_id = str(group.get("_id"))
                if not agent.get("group_id"):
                    self.agent_model.update_agent(agent_id, {"group_id": group_id, "status": agent.get("status", "pending")})

            current_global_version = self.model.get_global_version()
            current_group_version = group.get("whitelist_version", 1)

            # Check if agent has an active policy override BEFORE version short-circuit.
            # Skip version cache if:
            #   1. Policy is currently active (isolate/custom_whitelist) → agent needs policy-modified whitelist
            #   2. Policy changed since last sync (e.g. was isolate, now none) → agent needs fresh normal whitelist
            policy_changed = False
            if self.policy_service:
                effective_mode = self.policy_service.policy_model.get_effective_mode(agent_id)
                if effective_mode != "none" or effective_mode != agent_policy_mode:
                    policy_changed = True

            if not policy_changed and global_version == current_global_version and group_version == current_group_version:
                return {
                    "domains": [],
                    "timestamp": now_iso(),
                    "count": 0,
                    "type": "versioned",
                    "success": True,
                    "server_time": now_iso(),
                    "global_version": current_global_version,
                    "group_version": current_group_version,
                    "group_id": str(group.get("_id")),
                    "up_to_date": True,
                }
            global_entries = self.model.get_entries_for_sync(scope="global")

            # Check for active whitelist profile - overrides group base whitelist
            active_profile = None
            if self.profile_service:
                active_profile = self.profile_service.get_active_profile(str(group.get("_id")))

            if active_profile:
                # Use active profile's domains instead of group base whitelist
                profile_group = dict(group)
                profile_group["whitelist"] = active_profile.get("domains", [])
                group_entries = self._normalize_group_entries(profile_group, include_inactive=False)
            else:
                # Use group.whitelist as base
                group_entries = self._normalize_group_entries(group, include_inactive=False)

            combined = self._merge_whitelists(global_entries, group_entries)

            # ── Apply per-agent policy override (isolate / custom_whitelist) ──
            policy_mode = "none"
            policy_active = False
            if self.policy_service:
                try:
                    from flask import request as _req
                    server_host = _req.host.split(":")[0] if _req else None
                except Exception:
                    server_host = None

                policy_result = self.policy_service.apply_policy_to_sync(
                    agent_id, combined, server_host=server_host
                )
                combined = policy_result["domains"]
                policy_mode = policy_result["policy_mode"]
                policy_active = policy_result["policy_active"]

            response = {
                "domains": combined,
                "timestamp": now_iso(),
                "count": len(combined),
                "type": "full",
                "success": True,
                "server_time": now_iso(),
                "global_version": current_global_version,
                "group_version": current_group_version,
                "group_id": str(group.get("_id")),
                "agent_id": agent_id,
                "policy_mode": policy_mode,
                "policy_active": policy_active,
            }

            return response
            
        except Exception as e:
            self.logger.error(f"Error in agent sync: {e}")
            return {
                "domains": [],
                "timestamp": now_iso(),
                "count": 0,
                "type": "error",
                "success": False,
                "error": str(e),
                "server_time": now_iso(),
                "changes": {"added": [], "removed": [], "modified": [], "active_domains": []}
            }
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry from global or group scope"""
        
        # Try finding in global whitelist first
        entry = self.model.find_entry_by_id(entry_id)
        if entry:
            success = self.model.delete_entry(entry_id)
            if success and self.socketio:
                self.socketio.emit("whitelist_deleted", {
                    "id": entry_id,
                    "value": entry.get("value"),
                    "type": entry.get("type", "domain"),
                    "timestamp": now_iso()
                })
            return success
        
        # If not, it might be inside a group document?
        # But wait, group entries don't have unique IDs in whitelist list usually unless we assign them.
        # Front end sends IDs for deletion?
        # The frontend code sends `itemId` which for groups is usually missing in current impl unless normalized.
        
        # If the ID fails, we can't delete it easily here.
        # The controller needs to handle group item deletion separately or we need to search groups.
        # But this method signature takes an ID string.
        
        raise ValueError("Entry not found")

    def bulk_delete_entries(self, item_ids: List[str]) -> Dict:
        """Bulk delete multiple whitelist entries (Global and Group)"""
        deleted_count = 0
        errors = []
        
        # Group deletes by group_id to optimize updates
        group_deletes = {} # group_id -> list of (value, type)
        
        for item_id in item_ids:
            try:
                if item_id.startswith("group::") or item_id.startswith("group|"):
                    # Parse group item ID: group::<group_id>::<type>::<value>
                    # Also support legacy separator | for backwards compat
                    sep = "::" if "::" in item_id else "|"
                    parts = item_id.split(sep, 3)
                    if len(parts) == 4:
                        _, gid, gtype, gvalue = parts
                        if gid not in group_deletes:
                            group_deletes[gid] = []
                        group_deletes[gid].append((gvalue, gtype))
                    else:
                        errors.append(f"Invalid group item ID: {item_id}")
                else:
                    # Global item
                    if self.delete_entry(item_id):
                        deleted_count += 1
                    else:
                        errors.append(f"Failed to delete {item_id}")
            except Exception as e:
                errors.append(f"Error processing {item_id}: {str(e)}")
        
        # Process group deletes
        for gid, items in group_deletes.items():
            try:
                group = self.group_model.find_by_id(gid)
                if group:
                    original_len = len(group.get("whitelist", []))
                    # Filter out items to be deleted
                    # items is list of (value, type)
                    new_whitelist = []
                    for entry in group.get("whitelist", []):
                        # Normalize entry
                        e_val = entry.get("value") if isinstance(entry, dict) else entry
                        e_type = entry.get("type", "domain") if isinstance(entry, dict) else "domain"
                        
                        # Check if should be deleted
                        should_delete = False
                        for d_val, d_type in items:
                            if d_val == e_val and d_type == e_type:
                                should_delete = True
                                break
                        
                        if not should_delete:
                            new_whitelist.append(entry)
                    
                    if len(new_whitelist) != original_len:
                        self.group_model.update_group(gid, {
                            "whitelist": new_whitelist,
                            "whitelist_version": group.get("whitelist_version", 1) + 1
                        })
                        deleted_count += (original_len - len(new_whitelist))
            except Exception as e:
                errors.append(f"Error updating group {gid}: {str(e)}")

        return {
            "success": True,
            "deleted_count": deleted_count,
            "error_count": len(errors),
            "errors": errors[:10],
            "server_time": now_iso()
        }
    
    def bulk_add_entries(self, entries_data: List[Dict], client_ip: str) -> Dict:
        """Bulk add entries to whitelist - now with group support"""
        if not entries_data:
            raise ValueError("No entries provided")
        
        if len(entries_data) > 1000:
            raise ValueError("Maximum 1000 entries allowed per bulk operation")
        
        current_time = now_vietnam()
        
        # Split into global and group-specific entries
        global_entries = []
        group_entries_map = {}  # group_id -> [entries]
        errors = []
        
        for i, entry_data in enumerate(entries_data):
            try:
                entry_type = entry_data.get("type", "domain")
                value = entry_data.get("value", "").strip().lower()
                scope = entry_data.get("scope", "global")
                group_id = entry_data.get("group_id")
                
                if not value:
                    errors.append(f"Entry {i+1}: Value is required")
                    continue
                
                validation_result = self.model.validate_entry_value(entry_type, value)
                if not validation_result["valid"]:
                    errors.append(f"Entry {i+1}: {validation_result['message']}")
                    continue
                
                # Check duplicates in current batch (within same scope)
                if scope == "group" and group_id:
                    batch_group = group_entries_map.get(group_id, [])
                    if any(e.get("value") == value for e in batch_group):
                        errors.append(f"Entry {i+1}: Duplicate value in batch (group)")
                        continue
                else:
                    if any(e.get("value") == value for e in global_entries):
                        errors.append(f"Entry {i+1}: Duplicate value in batch (global)")
                        continue
                
                # Process entry
                processed_entry = {
                    "type": entry_type,
                    "value": value,
                    "category": entry_data.get("category", "uncategorized"),
                    "notes": entry_data.get("notes", "Bulk import"),
                    "priority": entry_data.get("priority", "normal"),
                    "added_by": client_ip,
                    "added_date": current_time,
                    "is_active": True
                }

                if scope == "group" and group_id:
                    if group_id not in group_entries_map:
                        group_entries_map[group_id] = []
                    group_entries_map[group_id].append(processed_entry)
                else:
                    # Check global duplicate
                    existing = self.model.find_entry_by_value(value)
                    if existing:
                        errors.append(f"Entry {i+1}: Global entry already exists")
                        continue
                    global_entries.append(processed_entry)
                
            except Exception as e:
                errors.append(f"Entry {i+1}: {str(e)}")
        
        # Insert Global Entries
        inserted_ids = []
        if global_entries:
            inserted_ids = self.model.bulk_insert_entries(global_entries)
        
        # Update Group Entries
        group_success_count = 0
        for grp_id, entries in group_entries_map.items():
            try:
                # Need to update group document
                group = self.group_model.find_by_id(grp_id)
                if not group:
                    errors.append(f"Group {grp_id} not found for bulk import")
                    continue
                
                current_whitelist = group.get("whitelist", [])
                
                # Filter out duplicates
                new_unique = []
                for ne in entries:
                    if not any(curr.get("value") == ne["value"] and curr.get("type") == ne["type"] for curr in current_whitelist):
                        new_unique.append(ne)
                    else:
                        errors.append(f"Entry {ne['value']} already exists in group {group.get('name')}")

                if new_unique:
                    updated_whitelist = current_whitelist + new_unique
                    self.group_model.update_group(grp_id, {
                        "whitelist": updated_whitelist,
                        "whitelist_version": (group.get("whitelist_version", 1) + 1)
                    })
                    group_success_count += len(new_unique)
                    
            except Exception as e:
                errors.append(f"Failed to update group {grp_id}: {str(e)}")

        total_inserted = len(inserted_ids) + group_success_count
        
        # Notify
        if total_inserted > 0 and self.socketio:
            self.socketio.emit("whitelist_bulk_added", {
                "count": total_inserted,
                "added_by": client_ip,
                "timestamp": now_iso()
            })
        
        return {
            "inserted_count": total_inserted,
            "error_count": len(errors),
            "errors": errors[:10],
            "success": total_inserted > 0,
            "server_time": now_iso()
        }
    
    def get_statistics(self) -> Dict:
        """Get whitelist statistics - vietnam ONLY"""
        try:
            stats = self.model.get_statistics()
            stats["server_time"] = now_iso()  # vietnam ISO
            return stats
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "by_type": {},
                "error": str(e),
                "server_time": now_iso()  # vietnam ISO
            }
    
    def update_entry(self, entry_id: str, update_data: Dict) -> bool:
        """Update an entry - supports both global ObjectIds and group pseudo-IDs"""

        # Check if this is a group pseudo-ID (group::<gid>::<type>::<value>)
        if entry_id.startswith("group::") or entry_id.startswith("group|"):
            return self._update_group_entry(entry_id, update_data)

        entry = self.model.find_entry_by_id(entry_id)
        if not entry:
            raise ValueError("Entry not found")

        # Validate update data
        if 'value' in update_data:
            value = update_data['value'].strip().lower()
            entry_type = update_data.get('type', entry.get('type', 'domain'))

            validation_result = self.model.validate_entry_value(entry_type, value)
            if not validation_result["valid"]:
                raise ValueError(validation_result["message"])

            update_data['value'] = value

        # Update timestamp
        update_data['updated_at'] = now_vietnam()

        success = self.model.update_entry(entry_id, update_data)

        if success and self.socketio:
            self.socketio.emit("whitelist_updated", {
                "id": entry_id,
                "value": update_data.get('value', entry.get('value')),
                "type": update_data.get('type', entry.get('type', 'domain')),
                "timestamp": now_iso()
            })

        return success

    def _update_group_entry(self, pseudo_id: str, update_data: Dict) -> bool:
        """Update a group whitelist entry identified by pseudo-ID.

        Supports toggling `is_active` (used to soft-disable entries without
        removing them). Legacy string entries are upgraded to dict so the
        toggle persists.
        """
        sep = "::" if "::" in pseudo_id else "|"
        parts = pseudo_id.split(sep, 3)
        if len(parts) != 4:
            raise ValueError(f"Invalid group entry ID: {pseudo_id}")

        _, gid, gtype, gvalue = parts
        group = self.group_model.find_by_id(gid)
        if not group:
            raise ValueError(f"Group {gid} not found")

        whitelist = group.get("whitelist", [])
        updated = False
        for i, entry in enumerate(whitelist):
            e_val = entry.get("value") if isinstance(entry, dict) else entry
            e_type = entry.get("type", "domain") if isinstance(entry, dict) else "domain"
            if e_val == gvalue and e_type == gtype:
                # Upgrade legacy string entry to dict so updates can persist.
                if not isinstance(entry, dict):
                    entry = {
                        "value": e_val,
                        "type": e_type,
                        "category": "uncategorized",
                        "priority": "normal",
                        "is_active": True,
                    }
                    whitelist[i] = entry

                for k, v in update_data.items():
                    if k in ("updated_at",):
                        continue
                    # Coerce is_active to bool to avoid string "false" being truthy.
                    if k == "is_active":
                        entry[k] = bool(v)
                    else:
                        entry[k] = v
                updated = True
                break

        if updated:
            self.group_model.update_group(gid, {"whitelist": whitelist})
        return updated

    def _delete_group_entry(self, group_id: str, value: str, entry_type: str = "domain") -> bool:
        """Delete an entry from a group's whitelist by value and type."""
        group = self.group_model.find_by_id(group_id)
        if not group:
            return False

        whitelist = group.get("whitelist", [])
        original_len = len(whitelist)
        whitelist = [
            e for e in whitelist
            if not (
                (e.get("value") if isinstance(e, dict) else e) == value
                and (e.get("type", "domain") if isinstance(e, dict) else "domain") == entry_type
            )
        ]

        if len(whitelist) < original_len:
            self.group_model.update_group(group_id, {"whitelist": whitelist})
            return True
        return False

    # sync_for_agent removed - dead code, replaced by get_agent_sync_data()

    def get_all_domains(self, limit: int = 100, offset: int = 0, search: str = None) -> Dict:
        """Get all domains with pagination - vietnam ONLY"""
        try:
            # Build query
            query = {}
            if search:
                query["$or"] = [
                    {"value": {"$regex": search, "$options": "i"}},
                    {"category": {"$regex": search, "$options": "i"}}
                ]
            
            # Get domains
            domains = self.model.find_all_entries(query)
            
            # Apply pagination
            total_count = len(domains)
            paginated_domains = domains[offset:offset + limit]
            
            return {
                "success": True,
                "domains": paginated_domains,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "server_time": now_iso()  # vietnam ISO
            }
            
        except Exception as e:
            self.logger.error(f"Error getting all domains: {e}")
            return {
                "success": False,
                "error": str(e),
                "domains": [],
                "total": 0,
                "server_time": now_iso()  # vietnam ISO
            }
    
    def add_domain(self, domain_value: str, category: str = "general") -> Dict:
        """Add new domain to whitelist - vietnam ONLY"""
        try:
            # Check if domain already exists
            existing = self.model.find_entry_by_value(domain_value)
            if existing:
                return {
                    "success": False,
                    "error": "Domain already exists in whitelist",
                    "existing_entry": existing,
                    "server_time": now_iso()  # vietnam ISO
                }
            
            # Validate domain
            validation = self.model.validate_entry_value("domain", domain_value)
            if not validation.get("valid"):
                return {
                    "success": False,
                    "error": validation.get("message", "Invalid domain"),
                    "server_time": now_iso()  # vietnam ISO
                }
            
            # Create entry data
            entry_data = {
                "value": domain_value.strip().lower(),
                "type": "domain",
                "category": category,
                "is_active": True,
                "priority": "normal",
                "added_by": "admin"
            }
            
            # Insert domain
            entry_id = self.model.insert_entry(entry_data)
            
            return {
                "success": True,
                "entry_id": entry_id,
                "domain": domain_value,
                "category": category,
                "server_time": now_iso()  # vietnam ISO
            }
            
        except Exception as e:
            self.logger.error(f"Error adding domain {domain_value}: {e}")
            return {
                "success": False,
                "error": str(e),
                "server_time": now_iso()  # vietnam ISO
            }
    
    def delete_domain(self, domain_id: str) -> Dict:
        """Delete domain from whitelist - supports both global entries and group pseudo-IDs"""
        try:
            # Handle group pseudo-IDs: group::<gid>::<type>::<value>
            if domain_id.startswith("group::") or domain_id.startswith("group|"):
                sep = "::" if "::" in domain_id else "|"
                parts = domain_id.split(sep, 3)
                if len(parts) == 4:
                    _, gid, gtype, gvalue = parts
                    result = self._delete_group_entry(gid, gvalue, gtype)
                    if result:
                        return {"success": True, "domain_id": domain_id, "domain_value": gvalue, "server_time": now_iso()}
                    return {"success": False, "error": "Entry not found in group", "server_time": now_iso()}
                return {"success": False, "error": "Invalid group pseudo-ID format", "server_time": now_iso()}

            # Global entry: check if domain exists
            existing = self.model.find_entry_by_id(domain_id)
            if not existing:
                return {
                    "success": False,
                    "error": "Domain not found",
                    "server_time": now_iso()
                }

            success = self.model.delete_entry(domain_id)

            if success:
                return {
                    "success": True,
                    "domain_id": domain_id,
                    "domain_value": existing.get("value"),
                    "server_time": now_iso()
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to delete domain",
                    "server_time": now_iso()
                }
                
        except Exception as e:
            self.logger.error(f"Error deleting domain {domain_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "server_time": now_iso()  # vietnam ISO
            }
    
    def import_domains(self, domains: List[str], category: str = "imported") -> Dict:
        """Import multiple domains - vietnam ONLY"""
        try:
            added_count = 0
            duplicate_count = 0
            error_count = 0
            errors = []
            
            for domain in domains:
                try:
                    domain = domain.strip().lower()
                    if not domain:
                        continue
                    
                    # Check if already exists
                    if self.model.find_entry_by_value(domain):
                        duplicate_count += 1
                        continue
                    
                    # Validate domain
                    validation = self.model.validate_entry_value("domain", domain)
                    if not validation.get("valid"):
                        error_count += 1
                        errors.append(f"{domain}: {validation.get('message')}")
                        continue
                    
                    # Create entry
                    entry_data = {
                        "value": domain,
                        "type": "domain",
                        "category": category,
                        "is_active": True,
                        "priority": "normal",
                        "added_by": "import"
                    }
                    
                    self.model.insert_entry(entry_data)
                    added_count += 1
                    
                except Exception as e:
                    error_count += 1
                    errors.append(f"{domain}: {str(e)}")
            
            return {
                "success": True,
                "added_count": added_count,
                "duplicate_count": duplicate_count,
                "error_count": error_count,
                "errors": errors[:10],  # Limit error list
                "total_processed": len(domains),
                "server_time": now_iso()  # vietnam ISO
            }
            
        except Exception as e:
            self.logger.error(f"Error importing domains: {e}")
            return {
                "success": False,
                "error": str(e),
                "server_time": now_iso()  # vietnam ISO
            }
    
    def export_domains(self, format: str = "json", category: str = None) -> Dict:
        """Export domains in specified format - vietnam ONLY"""
        try:
            # Build query
            query = {}
            if category:
                query["category"] = category
            
            # Get domains
            domains = self.model.find_all_entries(query)
            
            if format == "txt":
                # Text format - one domain per line
                domain_list = [domain["value"] for domain in domains]
                text_data = "\n".join(domain_list)
                
                return {
                    "success": True,
                    "data": text_data,
                    "count": len(domain_list),
                    "format": format,
                    "server_time": now_iso()  # vietnam ISO
                }
            else:
                # JSON format
                return {
                    "success": True,
                    "data": domains,
                    "count": len(domains),
                    "format": format,
                    "server_time": now_iso()  # vietnam ISO
                }
                
        except Exception as e:
            self.logger.error(f"Error exporting domains: {e}")
            return {
                "success": False,
                "error": str(e),
                "server_time": now_iso()  #  ISO
            }