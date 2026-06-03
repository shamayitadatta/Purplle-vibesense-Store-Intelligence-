from pipeline.emit import make_event
from pipeline.zones import crossed_entry_line, determine_direction

class VisitorStateTracker:
    def __init__(self, store_id, camera_id):
        self.store_id = store_id
        self.camera_id = camera_id
        self.visitor_state = {}
        self.billing_visitors = set()
        self.recent_exits = []
        self.visitor_alias = {}
        # {
        #   visitor_id: {
        #     "inside": False,
        #     "last_zone": None,
        #     "last_point": None
        #   }
        # }
        
    def _get_state(self, visitor_id):
        if visitor_id not in self.visitor_state:
            self.visitor_state[visitor_id] = {
                "inside": False,
                "last_zone": None,
                "last_point": None,
                "zone_enter_time": None,
                "last_dwell_time": None,
                "first_seen_time": None,
                "zones_visited": set(),
                "billing_visits": 0,
                "entry_exits": 0,
                "is_staff": False
            }
        return self.visitor_state[visitor_id]

    def _check_staff_status(self, state, timestamp):
        if state["is_staff"]:
            return True
        
        if state["first_seen_time"] is None:
            return False
            
        score = 0
        duration_minutes = (timestamp - state["first_seen_time"]).total_seconds() / 60.0
        if duration_minutes > 8:
            score += 2
        if len(state["zones_visited"]) >= 4:
            score += 1
        if state["billing_visits"] >= 5:
            score += 1
        if state["entry_exits"] >= 3: # Let's say 3 times means many times
            score += 1
            
        if score >= 3:
            state["is_staff"] = True
            
        return state["is_staff"]

    def _resolve_id(self, visitor_id):
        return self.visitor_alias.get(visitor_id, visitor_id)

    def update_position(self, visitor_id, current_point, timestamp, entry_line=None, confidence=0.9):
        """
        Updates the position for a visitor and generates ENTRY/EXIT events if an entry line is provided.
        Returns a list of generated events.
        """
        original_visitor_id = visitor_id
        visitor_id = self._resolve_id(visitor_id)
        
        state = self._get_state(visitor_id)
        if state["first_seen_time"] is None:
            state["first_seen_time"] = timestamp
            
        events = []
        is_staff = self._check_staff_status(state, timestamp)
        
        last_point = state["last_point"]
        
        if entry_line and last_point:
            if crossed_entry_line(last_point, current_point, entry_line):
                direction = determine_direction(last_point, current_point, entry_line)
                
                if direction == "ENTRY" and not state["inside"]:
                    # Check for reentry
                    reentry_id = None
                    for exit_record in self.recent_exits:
                        dt = (timestamp - exit_record["exit_time"]).total_seconds() / 60.0
                        if dt <= 5.0: # Reentry within 5 minutes
                            # Could check distance or color hist here
                            reentry_id = exit_record["visitor_id"]
                            break
                            
                    if reentry_id:
                        # Map to the old ID
                        self.visitor_alias[original_visitor_id] = reentry_id
                        visitor_id = reentry_id
                        state = self._get_state(visitor_id)
                        state["inside"] = True
                        state["entry_exits"] += 1
                        is_staff = self._check_staff_status(state, timestamp)
                        events.append(make_event(self.store_id, self.camera_id, visitor_id, "REENTRY", timestamp, is_staff=is_staff, confidence=confidence))
                    else:
                        state["inside"] = True
                        state["entry_exits"] += 1
                        is_staff = self._check_staff_status(state, timestamp)
                        events.append(make_event(self.store_id, self.camera_id, visitor_id, "ENTRY", timestamp, is_staff=is_staff, confidence=confidence))
                elif direction == "EXIT" and state["inside"]:
                    state["inside"] = False
                    state["entry_exits"] += 1
                    is_staff = self._check_staff_status(state, timestamp)
                    events.append(make_event(self.store_id, self.camera_id, visitor_id, "EXIT", timestamp, is_staff=is_staff, confidence=confidence))
                    
                    self.recent_exits.append({
                        "visitor_id": visitor_id,
                        "exit_time": timestamp,
                        "last_point": current_point
                    })
                    
                    # Cleanup old exits
                    self.recent_exits = [e for e in self.recent_exits if (timestamp - e["exit_time"]).total_seconds() / 60.0 <= 5.0]

        state["last_point"] = current_point
        return events

    def update_zone(self, visitor_id, current_zone, timestamp, confidence=0.9):
        """
        Updates the zone for a visitor and generates ZONE_ENTER/ZONE_EXIT and ZONE_DWELL events.
        Returns a list of generated events.
        """
        visitor_id = self._resolve_id(visitor_id)
        state = self._get_state(visitor_id)
        if state["first_seen_time"] is None:
            state["first_seen_time"] = timestamp
            
        events = []
        is_staff = self._check_staff_status(state, timestamp)
        
        last_zone = state["last_zone"]
        
        # Check zone change
        if last_zone != current_zone:
            if last_zone is not None:
                events.append(make_event(self.store_id, self.camera_id, visitor_id, "ZONE_EXIT", timestamp, zone_id=last_zone, is_staff=is_staff, confidence=confidence))
                if last_zone == "BILLING" and visitor_id in self.billing_visitors:
                    self.billing_visitors.remove(visitor_id)
            
            if current_zone is not None:
                state["zones_visited"].add(current_zone)
                if current_zone == "BILLING":
                    state["billing_visits"] += 1
                
                is_staff = self._check_staff_status(state, timestamp)
                
                events.append(make_event(self.store_id, self.camera_id, visitor_id, "ZONE_ENTER", timestamp, zone_id=current_zone, is_staff=is_staff, confidence=confidence))
                state["zone_enter_time"] = timestamp
                state["last_dwell_time"] = timestamp
                
                if current_zone == "BILLING":
                    queue_depth = len(self.billing_visitors)
                    self.billing_visitors.add(visitor_id)
                    if queue_depth > 0:
                        events.append(make_event(
                            self.store_id, 
                            self.camera_id, 
                            visitor_id, 
                            "BILLING_QUEUE_JOIN", 
                            timestamp, 
                            zone_id="BILLING",
                            metadata={"queue_depth": queue_depth},
                            is_staff=is_staff,
                            confidence=confidence
                        ))
            else:
                state["zone_enter_time"] = None
                state["last_dwell_time"] = None
        else:
            # Same zone, check for dwell
            if current_zone is not None and state["last_dwell_time"] is not None:
                dt_seconds = (timestamp - state["last_dwell_time"]).total_seconds()
                if dt_seconds >= 30:
                    dwell_ms = int((timestamp - state["zone_enter_time"]).total_seconds() * 1000)
                    events.append(make_event(
                        self.store_id, 
                        self.camera_id, 
                        visitor_id, 
                        "ZONE_DWELL", 
                        timestamp, 
                        zone_id=current_zone,
                        dwell_ms=dwell_ms,
                        is_staff=is_staff,
                        confidence=confidence
                    ))
                    state["last_dwell_time"] = timestamp
                
        state["last_zone"] = current_zone
        return events
