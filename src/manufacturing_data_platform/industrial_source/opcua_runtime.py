"""Local OPC UA replay server and subscription collector for S-MFG-10."""

from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asyncua import Client, Server, ua

from manufacturing_data_platform.industrial_source.contracts import (
    REPLAY_MODE,
    SCHEMA_VERSION,
    SOURCE_TIME_ASSUMPTION,
    make_event_id,
)
from manufacturing_data_platform.industrial_source.report import (
    build_collection_report,
    persist_report,
)
from manufacturing_data_platform.industrial_source.source import (
    DATASET_DOI,
    DATASET_ID,
    EQUIPMENT_ID,
    MAPPING_VERSION,
    METROPT3_TAGS,
    OPCUA_NAMESPACE_URI,
    MetroPTSelection,
    MetroPTSourceRow,
    TagMapping,
)
from manufacturing_data_platform.industrial_source.spool import TelemetrySpool


class IndustrialSourceRuntimeError(RuntimeError):
    """The bounded local replay cannot prove its collection contract."""


class LocalMetroPTReplayServer:
    """Read-only local server surface; only this owner writes replay values."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.server = Server()
        self.namespace_index: int | None = None
        self.nodes: dict[str, Any] = {}

    async def initialize(self) -> None:
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name("MetroPT-3 bounded replay simulator")
        self.namespace_index = await self.server.register_namespace(OPCUA_NAMESPACE_URI)
        equipment = await self.server.nodes.objects.add_object(
            ua.NodeId("MetroPT3.APU", self.namespace_index),
            "MetroPT3 APU (simulated replay)",
        )

        for tag in METROPT3_TAGS:
            node = await equipment.add_variable(
                ua.NodeId(tag.opcua_identifier, self.namespace_index),
                tag.tag_id,
                ua.Variant(0.0, ua.VariantType.Double),
            )
            unit = ua.EUInformation(
                NamespaceUri=tag.engineering_unit.namespace_uri,
                UnitId=tag.engineering_unit.unit_id,
                DisplayName=ua.LocalizedText(tag.engineering_unit.display_name),
                Description=ua.LocalizedText(tag.engineering_unit.unit_code),
            )
            await node.add_property(
                ua.NodeId(
                    f"{tag.opcua_identifier}.EngineeringUnits", self.namespace_index
                ),
                ua.QualifiedName("EngineeringUnits", 0),
                unit,
                varianttype=ua.VariantType.ExtensionObject,
            )
            now = datetime.now(timezone.utc)
            await node.write_value(
                ua.DataValue(
                    Value=None,
                    StatusCode=ua.StatusCode(ua.StatusCodes.BadWaitingForInitialData),
                    SourceTimestamp=now,
                    ServerTimestamp=now,
                )
            )
            self.nodes[tag.tag_id] = node

    async def start(self) -> None:
        await self.server.start()

    async def stop(self) -> None:
        await self.server.stop()

    async def replay_observation(
        self,
        row: MetroPTSourceRow,
        tag: TagMapping,
        *,
        status_code: int = ua.StatusCodes.Good,
    ) -> None:
        status = ua.StatusCode(status_code)
        value = None if status.is_bad() else row.values[tag.tag_id]
        await self.nodes[tag.tag_id].write_value(
            ua.DataValue(
                Value=(
                    None
                    if value is None
                    else ua.Variant(value, ua.VariantType.Double)
                ),
                StatusCode=status,
                SourceTimestamp=row.replay_timestamp,
                ServerTimestamp=datetime.now(timezone.utc),
            )
        )


class _CollectorHandler:
    def __init__(
        self,
        *,
        selection: MetroPTSelection,
        replay_session_id: str,
        spool: TelemetrySpool,
        runtime_nodes: dict[str, tuple[TagMapping, str, dict[str, Any]]],
        fault_event_ids: set[str],
    ):
        self.selection = selection
        self.replay_session_id = replay_session_id
        self.spool = spool
        self.runtime_nodes = runtime_nodes
        self.fault_event_ids = fault_event_ids
        self.waiting_notification_count = 0
        self.unknown_mapping_count = 0
        self.errors: list[str] = []
        self.accepted_count = 0
        self._source_rows = {
            (row.replay_timestamp, tag.tag_id): row
            for row in selection.rows
            for tag in selection.tags
        }

    def datachange_notification(self, node, value, data) -> None:
        try:
            data_value = data.monitored_item.Value
            status = data_value.StatusCode
            if status.value == ua.StatusCodes.BadWaitingForInitialData:
                self.waiting_notification_count += 1
                return

            runtime_node_id = node.nodeid.to_string()
            mapping = self.runtime_nodes.get(runtime_node_id)
            if mapping is None:
                self.unknown_mapping_count += 1
                return
            tag, namespace_uri, engineering_unit = mapping

            source_timestamp = data_value.SourceTimestamp
            source_row = self._source_rows.get((source_timestamp, tag.tag_id))
            if source_row is None:
                self.unknown_mapping_count += 1
                return
            if data_value.ServerTimestamp is None:
                raise IndustrialSourceRuntimeError("serverTimestamp is required")

            event_id = make_event_id(
                self.selection.source_file_sha256,
                source_row.physical_row_number,
                tag.tag_id,
            )
            severity = _status_severity(status)
            event = {
                "schema_version": SCHEMA_VERSION,
                "event_id": event_id,
                "equipment_id": EQUIPMENT_ID,
                "tag_id": tag.tag_id,
                "opcua_namespace_uri": namespace_uri,
                "opcua_identifier": tag.opcua_identifier,
                "opcua_runtime_node_id": runtime_node_id,
                "value": None if severity == "bad" else value,
                "value_type": tag.value_type,
                "engineering_unit": engineering_unit,
                "status_code": status.value,
                "status_name": status.name,
                "status_severity": severity,
                "historical_timestamp_raw": source_row.historical_timestamp_raw,
                "historical_timezone": None,
                "source_timestamp": _iso_utc(source_timestamp),
                "source_time_assumption": SOURCE_TIME_ASSUMPTION,
                "server_timestamp": _iso_utc(data_value.ServerTimestamp),
                "collected_at": _iso_utc(datetime.now(timezone.utc)),
                "source_dataset_id": DATASET_ID,
                "source_dataset_doi": DATASET_DOI,
                "source_file_sha256": self.selection.source_file_sha256,
                "source_physical_row_number": source_row.physical_row_number,
                "source_index": source_row.source_index,
                "mapping_version": MAPPING_VERSION,
                "replay_session_id": self.replay_session_id,
                "replay_mode": REPLAY_MODE,
                "fault_injected": event_id in self.fault_event_ids,
            }
            self.spool.append(event)
            self.accepted_count += 1
        except Exception as exc:  # asyncua logs handler exceptions but cannot propagate them.
            self.errors.append(f"{type(exc).__name__}: {exc}")


class SubscriptionCollector:
    def __init__(
        self,
        *,
        endpoint: str,
        selection: MetroPTSelection,
        replay_session_id: str,
        spool: TelemetrySpool,
        fault_event_ids: set[str],
    ):
        self.endpoint = endpoint
        self.selection = selection
        self.replay_session_id = replay_session_id
        self.spool = spool
        self.fault_event_ids = fault_event_ids
        self.client: Client | None = None
        self.subscription = None
        self.handles: list[int | ua.StatusCode] = []
        self.handler: _CollectorHandler | None = None

    async def start(self) -> None:
        self.client = Client(self.endpoint)
        await self.client.connect()
        namespace_index = await self.client.get_namespace_index(OPCUA_NAMESPACE_URI)

        runtime_nodes: dict[str, tuple[TagMapping, str, dict[str, Any]]] = {}
        nodes = []
        for tag in self.selection.tags:
            node = self.client.get_node(ua.NodeId(tag.opcua_identifier, namespace_index))
            engineering_units_node = await node.get_child(
                ua.QualifiedName("EngineeringUnits", 0)
            )
            actual_unit = validate_engineering_unit(
                await engineering_units_node.read_value(), tag
            )
            runtime_nodes[node.nodeid.to_string()] = (
                tag,
                OPCUA_NAMESPACE_URI,
                actual_unit,
            )
            nodes.append(node)

        self.handler = _CollectorHandler(
            selection=self.selection,
            replay_session_id=self.replay_session_id,
            spool=self.spool,
            runtime_nodes=runtime_nodes,
            fault_event_ids=self.fault_event_ids,
        )
        self.subscription = await self.client.create_subscription(20, self.handler)
        data_change_filter = ua.DataChangeFilter(
            Trigger=ua.DataChangeTrigger.StatusValueTimestamp,
            DeadbandType=0,
            DeadbandValue=0,
        )
        requests = [
            _monitored_item_request(
                node=node,
                client_handle=1_000 + position,
                data_change_filter=data_change_filter,
            )
            for position, node in enumerate(nodes, start=1)
        ]
        self.handles = await self.subscription.create_monitored_items(requests)
        failed = [handle for handle in self.handles if isinstance(handle, ua.StatusCode)]
        if failed:
            raise IndustrialSourceRuntimeError(
                f"failed to create monitored items: {failed}"
            )
        await _wait_for(
            lambda: bool(self.handler)
            and self.handler.waiting_notification_count >= len(nodes),
            "initial BadWaitingForInitialData notifications",
        )

    async def wait_for_accepted(self, count: int) -> None:
        await _wait_for(
            lambda: bool(self.handler) and self.handler.accepted_count >= count,
            f"{count} accepted observations",
        )
        self.raise_handler_errors()

    def raise_handler_errors(self) -> None:
        if self.handler and self.handler.errors:
            raise IndustrialSourceRuntimeError(
                "collector callback failed: " + "; ".join(self.handler.errors)
            )

    async def close(self) -> None:
        try:
            if self.subscription is not None:
                if self.handles:
                    await self.subscription.unsubscribe(self.handles)
                await self.subscription.delete()
        finally:
            if self.client is not None:
                await self.client.disconnect()
        self.subscription = None
        self.client = None


async def run_collection_scenario(
    *,
    selection: MetroPTSelection,
    scenario: str,
    output_root: str | Path,
) -> dict[str, Any]:
    if scenario not in {"normal", "quality", "interrupted"}:
        raise ValueError("scenario must be normal, quality, or interrupted")

    endpoint = f"opc.tcp://127.0.0.1:{_available_loopback_port()}/metropt3/"
    replay_session_id = f"fixture-{scenario}"
    spool = TelemetrySpool(Path(output_root) / "spool", replay_session_id)
    fault_codes = _fault_plan(selection) if scenario == "quality" else {}
    fault_event_ids = set(fault_codes)

    server = LocalMetroPTReplayServer(endpoint)
    await server.initialize()
    collector = SubscriptionCollector(
        endpoint=endpoint,
        selection=selection,
        replay_session_id=replay_session_id,
        spool=spool,
        fault_event_ids=fault_event_ids,
    )
    server_started = False
    collector_active = False
    try:
        await server.start()
        server_started = True
        await collector.start()
        collector_active = True
        accepted_target = 0
        for row_index, row in enumerate(selection.rows, start=1):
            for tag in selection.tags:
                event_id = make_event_id(
                    selection.source_file_sha256,
                    row.physical_row_number,
                    tag.tag_id,
                )
                await server.replay_observation(
                    row, tag, status_code=fault_codes.get(event_id, ua.StatusCodes.Good)
                )
            accepted_target += len(selection.tags)
            if scenario == "interrupted" and row_index == 1:
                await collector.wait_for_accepted(accepted_target)
                await collector.close()
                collector_active = False
            elif collector_active:
                await collector.wait_for_accepted(accepted_target)
        if collector_active:
            collector.raise_handler_errors()
    finally:
        try:
            if collector.client is not None:
                await collector.close()
        finally:
            if server_started:
                await server.stop()

    spool.write_seal(
        expected_event_ids=selection.expected_event_ids,
        source_file_sha256=selection.source_file_sha256,
        mapping_version=MAPPING_VERSION,
    )
    handler = collector.handler
    if handler is None:
        raise IndustrialSourceRuntimeError("collector handler was not initialized")
    report = build_collection_report(
        scenario=scenario,
        selection=selection,
        events=spool.load_events(),
        waiting_notification_count=handler.waiting_notification_count,
        duplicate_count=spool.duplicate_count,
        conflict_count=spool.conflict_count,
        unknown_mapping_count=handler.unknown_mapping_count,
    )
    report_path, pointer_path = persist_report(output_root, report)
    report["report_path"] = str(report_path)
    report["last_good_path"] = str(pointer_path) if pointer_path else None
    return report


def _fault_plan(selection: MetroPTSelection) -> dict[str, int]:
    return {
        make_event_id(
            selection.source_file_sha256,
            selection.rows[1].physical_row_number,
            selection.tags[0].tag_id,
        ): ua.StatusCodes.UncertainSubstituteValue,
        make_event_id(
            selection.source_file_sha256,
            selection.rows[2].physical_row_number,
            selection.tags[2].tag_id,
        ): ua.StatusCodes.BadNoData,
    }


def _status_severity(status: ua.StatusCode) -> str:
    if status.is_good():
        return "good"
    if status.is_uncertain():
        return "uncertain"
    return "bad"


def validate_engineering_unit(
    value: ua.EUInformation, tag: TagMapping
) -> dict[str, Any]:
    actual = {
        "namespace_uri": value.NamespaceUri,
        "unit_code": value.Description.Text or tag.engineering_unit.unit_code,
        "unit_id": value.UnitId,
        "display_name": value.DisplayName.Text,
    }
    expected = tag.engineering_unit.as_dict()
    if actual != expected:
        raise IndustrialSourceRuntimeError(
            f"{tag.tag_id} EngineeringUnits mismatch: "
            f"expected {expected}, got {actual}"
        )
    return actual


def _monitored_item_request(
    *, node, client_handle: int, data_change_filter: ua.DataChangeFilter
) -> ua.MonitoredItemCreateRequest:
    value = ua.ReadValueId(NodeId=node.nodeid, AttributeId=ua.AttributeIds.Value)
    parameters = ua.MonitoringParameters(
        ClientHandle=client_handle,
        SamplingInterval=0,
        Filter=data_change_filter,
        QueueSize=10,
        DiscardOldest=True,
    )
    return ua.MonitoredItemCreateRequest(
        ItemToMonitor=value,
        MonitoringMode=ua.MonitoringMode.Reporting,
        RequestedParameters=parameters,
    )


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def _wait_for(predicate, description: str, timeout: float = 5.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.01)

    try:
        await asyncio.wait_for(poll(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise IndustrialSourceRuntimeError(f"timed out waiting for {description}") from exc
