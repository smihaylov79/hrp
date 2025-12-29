from django import template

register = template.Library()

@register.filter
def index(sequence, position):
    """
    Връща елемент от списък по индекс.
    Пример: {{ mylist|index:0 }} -> първия елемент
    """
    try:
        return sequence[position]
    except (IndexError, TypeError):
        return ''


@register.filter
def grand_total(proposal_rows):
    """
    Връща сумата на всички 'total' стойности от proposal_rows.
    """
    if not proposal_rows:
        return 0
    return sum(row.get("total", 0) for row in proposal_rows)