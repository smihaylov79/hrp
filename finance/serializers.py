from rest_framework import serializers
from .models import Market
from datetime import timedelta


class MarketSerializer(serializers.ModelSerializer):
    is_open_now = serializers.SerializerMethodField()
    time_until_event = serializers.SerializerMethodField()

    class Meta:
        model = Market
        fields = [
            'id',
            'name',
            'time_zone',
            'open_time',
            'close_time',
            'is_open_now',
            'time_until_event',
        ]

    def get_is_open_now(self, obj):
        return obj.is_open_now()

    def get_time_until_event(self, obj):
        delta = obj.time_until_event()
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m"