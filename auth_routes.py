"""
Flask Authentication Routes
===========================
API endpoints for authentication and user management.
"""

from flask import Blueprint, jsonify, request

from auth_core import UserRole, UserStatus
from auth_middleware import AuthMiddleware
from auth_service import AuthenticationService, AuthorizationService, UserManagementService


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def init_auth_routes(
    auth_service: AuthenticationService,
    authz_service: AuthorizationService,
    user_mgmt_service: UserManagementService,
    auth_middleware: AuthMiddleware
):
    """Initialize authentication routes with dependencies."""
    
    @auth_bp.route('/login/admin', methods=['POST'])
    def login_admin():
        """Admin login endpoint."""
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            if not username or not password:
                return jsonify({"error": "Username and password required"}), 400
            
            
            admin = auth_service.authenticate_admin(username, password)
            if not admin:
                return jsonify({"error": "Invalid credentials"}), 401
            
            
            ip_address = request.remote_addr
            session = auth_service.create_session(admin, ip_address)
            
            response = jsonify({
                "message": "Login successful",
                "session_id": session.session_id,
                "user": {
                    "id": admin.id,
                    "username": admin.username,
                    "role": admin.role.value,
                    "email": admin.email
                }
            })
            
            
            response.set_cookie('session_id', session.session_id, httponly=True, 
                              secure=False, samesite='Lax', max_age=86400)
            
            return response, 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/login/player', methods=['POST'])
    def login_player():
        """Player login endpoint (using name and DOB)."""
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            dob = data.get('date_of_birth', '').strip()
            
            if not name or not dob:
                return jsonify({"error": "Name and date of birth required"}), 400
            
            
            player = auth_service.authenticate_player(name, dob)
            if not player:
                return jsonify({"error": "Invalid credentials"}), 401
            
            
            ip_address = request.remote_addr
            session = auth_service.create_session(player, ip_address)
            
            response = jsonify({
                "message": "Login successful",
                "session_id": session.session_id,
                "user": {
                    "id": player.id,
                    "name": player.name,
                    "player_id": player.player_id,
                    "role": player.role.value,
                    "status": player.status.value
                }
            })
            
            response.set_cookie('session_id', session.session_id, httponly=True,
                              secure=False, samesite='Lax', max_age=86400)
            
            return response, 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/logout', methods=['POST'])
    @auth_middleware.require_auth
    def logout():
        """Logout endpoint."""
        try:
            session = auth_middleware.get_current_session()
            if session:
                auth_service.invalidate_session(session.session_id)
            
            response = jsonify({"message": "Logged out successfully"})
            response.set_cookie('session_id', '', expires=0)
            return response, 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/register/player', methods=['POST'])
    def register_player():
        """Player registration endpoint."""
        try:
            data = request.get_json()
            player_id = data.get('player_id', '').strip()
            name = data.get('name', '').strip()
            dob = data.get('date_of_birth', '').strip()
            
            if not player_id or not name or not dob:
                return jsonify({"error": "Player ID, name, and date of birth required"}), 400
            
            
            player = user_mgmt_service.register_player(player_id, name, dob)
            
            return jsonify({
                "message": "Registration successful",
                "user": {
                    "id": player.id,
                    "name": player.name,
                    "player_id": player.player_id
                }
            }), 201
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/me', methods=['GET'])
    @auth_middleware.require_auth
    def get_current_user():
        """Get current user information."""
        try:
            user = auth_middleware.get_current_user()
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            user_data = {
                "id": user.id,
                "role": user.role.value,
                "status": user.status.value,
                "created_at": user.created_at,
                "last_login": user.last_login
            }
            
            
            if user.role == UserRole.ADMIN:
                user_data.update({
                    "username": user.username,
                    "email": user.email
                })
            elif user.role == UserRole.PLAYER:
                user_data.update({
                    "name": user.name,
                    "player_id": user.player_id,
                    "date_of_birth": user.date_of_birth
                })
            
            return jsonify(user_data), 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/admin/change-password', methods=['POST'])
    @auth_middleware.require_admin
    def change_password():
        """Change admin password."""
        try:
            data = request.get_json()
            current_password = data.get('current_password', '')
            new_password = data.get('new_password', '')
            
            if not current_password or not new_password:
                return jsonify({"error": "Current and new password required"}), 400
            
            user = auth_middleware.get_current_user()
            user_mgmt_service.change_admin_password(user.id, current_password, new_password)
            
            return jsonify({"message": "Password changed successfully"}), 200
            
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/admin/suspend-user/<user_id>', methods=['POST'])
    @auth_middleware.require_admin
    def suspend_user(user_id):
        """Suspend a user (admin only)."""
        try:
            data = request.get_json() or {}
            reason = data.get('reason', '')
            
            admin = auth_middleware.get_current_user()
            user_mgmt_service.suspend_user(user_id, admin.id, reason)
            
            return jsonify({"message": "User suspended successfully"}), 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/admin/shadow-ban-user/<user_id>', methods=['POST'])
    @auth_middleware.require_admin
    def shadow_ban_user(user_id):
        """Shadow ban a user (admin only)."""
        try:
            data = request.get_json() or {}
            reason = data.get('reason', '')
            
            admin = auth_middleware.get_current_user()
            user_mgmt_service.shadow_ban_user(user_id, admin.id, reason)
            
            return jsonify({"message": "User shadow banned successfully"}), 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @auth_bp.route('/admin/reactivate-user/<user_id>', methods=['POST'])
    @auth_middleware.require_admin
    def reactivate_user(user_id):
        """Reactivate a suspended/banned user (admin only)."""
        try:
            admin = auth_middleware.get_current_user()
            user_mgmt_service.reactivate_user(user_id, admin.id)
            
            return jsonify({"message": "User reactivated successfully"}), 200
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return auth_bp