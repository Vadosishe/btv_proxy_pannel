import logging
from sqlalchemy.orm import Session
from app.models import ClientKey, Node, ProtocolType
from app.services.amnezia import AmneziaClient
from app.config import settings

logger = logging.getLogger("b2b_sync")

async def sync_remote_amnezia_keys(db: Session):
    """
    Full Two-Way Synchronization:
    1. Removes keys from B2B DB if deleted in amneziavpnphp panel.
    2. Imports keys into B2B DB if created directly inside amneziavpnphp panel.
    """
    from app.models import Agency
    default_agency = db.query(Agency).first()
    default_agency_id = default_agency.id if default_agency else 1

    awg_nodes = db.query(Node).filter(Node.node_type == "amnezia").all()
    
    for node in awg_nodes:
        if not node.amnezia_server_id:
            continue
        try:
            amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
            amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
            remote_res = await amnezia.list_server_clients(node.amnezia_server_id)
            
            if not remote_res.get("success"):
                continue

            remote_clients = remote_res.get("clients", [])
            active_remote_ids = {str(c["id"]) for c in remote_clients}

            local_keys = db.query(ClientKey).filter(
                ClientKey.node_id == node.id,
                ClientKey.protocol == ProtocolType.AMNEZIA_WG
            ).all()

            existing_local_remote_ids = {k.remote_client_id for k in local_keys if k.remote_client_id}

            # 1. Purge local keys that were deleted on panel
            for k in local_keys:
                if k.remote_client_id and k.remote_client_id not in active_remote_ids:
                    logger.info(f"Key ID {k.id} ({k.employee_name}) was deleted in amneziavpnphp. Removing from B2B DB.")
                    db.delete(k)

            # 2. Import remote keys created directly in panel
            for remote_c in remote_clients:
                rc_id = str(remote_c["id"])
                if rc_id not in existing_local_remote_ids:
                    c_name = remote_c.get("name", f"Amnezia Client {rc_id}")
                    details = await amnezia.get_client_details(rc_id)
                    conf = details.get("vpn_link") or details.get("config") or amnezia._format_vpn_uri(details.get("config", ""))
                    
                    new_key = ClientKey(
                        agency_id=default_agency_id,
                        node_id=node.id,
                        employee_name=c_name,
                        protocol=ProtocolType.AMNEZIA_WG,
                        config_content=conf,
                        remote_client_id=rc_id
                    )
                    db.add(new_key)
                    logger.info(f"Imported client {rc_id} ({c_name}) created directly in amneziavpnphp into B2B DB.")

            db.commit()
        except Exception as e:
            logger.error(f"Error syncing Amnezia node {node.id}: {e}")

