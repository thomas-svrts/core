"""Support for MQTT locks."""
import functools

import voluptuous as vol

from homeassistant.components import lock
from homeassistant.components.lock import LockEntity
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from . import PLATFORMS, subscription
from .. import mqtt
from .const import CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN, CONF_STATE_TOPIC, DOMAIN
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

CONF_PAYLOAD_LOCK = "payload_lock"
CONF_PAYLOAD_UNLOCK = "payload_unlock"

CONF_STATE_LOCKED = "state_locked"
CONF_STATE_UNLOCKED = "state_unlocked"

DEFAULT_NAME = "MQTT Lock"
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_LOCK = "LOCK"
DEFAULT_PAYLOAD_UNLOCK = "UNLOCK"
DEFAULT_STATE_LOCKED = "LOCKED"
DEFAULT_STATE_UNLOCKED = "UNLOCKED"

MQTT_LOCK_ATTRIBUTES_BLOCKED = frozenset(
    {
        lock.ATTR_CHANGED_BY,
        lock.ATTR_CODE_FORMAT,
    }
)

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_LOCK, default=DEFAULT_PAYLOAD_LOCK): cv.string,
        vol.Optional(CONF_PAYLOAD_UNLOCK, default=DEFAULT_PAYLOAD_UNLOCK): cv.string,
        vol.Optional(CONF_STATE_LOCKED, default=DEFAULT_STATE_LOCKED): cv.string,
        vol.Optional(CONF_STATE_UNLOCKED, default=DEFAULT_STATE_UNLOCKED): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT lock panel through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT lock dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, lock.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT Lock platform."""
    async_add_entities([MqttLock(hass, config, config_entry, discovery_data)])


class MqttLock(MqttEntity, LockEntity):
    """Representation of a lock that can be toggled using MQTT."""

    _attributes_extra_blocked = MQTT_LOCK_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the lock."""
        self._state = False
        self._optimistic = False

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._optimistic = config[CONF_OPTIMISTIC]

        value_template = self._config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = self.hass

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            payload = msg.payload
            value_template = self._config.get(CONF_VALUE_TEMPLATE)
            if value_template is not None:
                payload = value_template.async_render_with_possible_json_value(payload)
            if payload == self._config[CONF_STATE_LOCKED]:
                self._state = True
            elif payload == self._config[CONF_STATE_UNLOCKED]:
                self._state = False

            self.async_write_ha_state()

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = await subscription.async_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": message_received,
                        "qos": self._config[CONF_QOS],
                    }
                },
            )

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    async def async_lock(self, **kwargs):
        """Lock the device.

        This method is a coroutine.
        """
        await mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_LOCK],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            # Optimistically assume that the lock has changed state.
            self._state = True
            self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the device.

        This method is a coroutine.
        """
        await mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_UNLOCK],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            # Optimistically assume that the lock has changed state.
            self._state = False
            self.async_write_ha_state()
