# API документация: Удаление сущностей и изменение связей

## Обзор

Данная документация описывает API для удаления групп (subsets), инструментов (tools) и изменения связей между сущностями проекта.

---

## Удаление групп (Subsets)

### `Project.delete_subset(subset_id: int) -> None`

Удаляет группу сравнения из проекта.

**Параметры:**
- `subset_id` (int): ID группы для удаления

**Возвращает:**
- `None`

**Исключения:**
- `ValueError`: Если группа имеет связанные образцы

**Поведение:**
1. Проверяет наличие образцов, привязанных к группе
2. Если образцы есть → выбрасывает `ValueError` с количеством образцов
3. Если образцов нет → удаляет группу из базы данных
4. Автоматически сохраняет изменения

**Пример использования:**

```python
async def delete_empty_group():
    async with Project("myproject.dasmix") as project:
        try:
            await project.delete_subset(subset_id=5)
            print("Group deleted successfully")
        except ValueError as e:
            print(f"Cannot delete: {e}")
            # Output: "Cannot delete: 3 samples are associated with it"
```

**SQL запросы:**
```sql
-- Проверка наличия образцов
SELECT COUNT(*) as cnt FROM sample WHERE subset_id = ?

-- Удаление группы
DELETE FROM subset WHERE id = ?
```

**Связанные методы:**
- `get_subsets()` - получить список всех групп
- `get_subset(subset_id)` - получить группу по ID
- `add_subset(name, details, display_color)` - создать группу

---

## Удаление инструментов (Tools)

### `Project.delete_tool(tool_id: int) -> None`

Удаляет инструмент идентификации из проекта.

**Параметры:**
- `tool_id` (int): ID инструмента для удаления

**Возвращает:**
- `None`

**Исключения:**
- `ValueError`: Если инструмент имеет связанные идентификации

**Поведение:**
1. Проверяет наличие идентификаций, связанных с инструментом
2. Если идентификации есть → выбрасывает `ValueError` с количеством идентификаций
3. Если идентификаций нет → удаляет инструмент из базы данных
4. Автоматически сохраняет изменения

**Пример использования:**

```python
async def delete_unused_tool():
    async with Project("myproject.dasmix") as project:
        try:
            await project.delete_tool(tool_id=3)
            print("Tool deleted successfully")
        except ValueError as e:
            print(f"Cannot delete: {e}")
            # Output: "Cannot delete: 1250 identifications are associated with it"
```

**SQL запросы:**
```sql
-- Проверка наличия идентификаций
SELECT COUNT(*) as cnt FROM identification WHERE tool_id = ?

-- Удаление инструмента
DELETE FROM tool WHERE id = ?
```

**Связанные методы:**
- `get_tools()` - получить список всех инструментов
- `get_tool(tool_id)` - получить инструмент по ID
- `add_tool(name, type, settings, display_color)` - создать инструмент

---

## Изменение группы образца

### `Project.update_sample(sample: Sample) -> None`

Обновляет данные образца, включая изменение группы.

**Параметры:**
- `sample` (Sample): Объект образца с обновленными данными

**Возвращает:**
- `None`

**Исключения:**
- `ValueError`: Если образец не имеет ID
- (другие исключения базы данных при некорректных данных)

**Поведение:**
1. Проверяет наличие ID у образца
2. Обновляет запись в базе данных
3. Автоматически сохраняет изменения

**Пример использования:**

```python
async def change_sample_group():
    async with Project("myproject.dasmix") as project:
        # Получить образец
        sample = await project.get_sample_by_name("Sample_001")
        
        # Изменить группу
        sample.subset_id = 5  # Новая группа
        # или
        sample.subset_id = None  # Убрать из всех групп
        
        # Сохранить изменения
        await project.update_sample(sample)
        print(f"Sample group updated to {sample.subset_id}")
```

**SQL запросы:**
```sql
UPDATE sample 
SET name = ?, subset_id = ?, additions = ? 
WHERE id = ?
```

**Связанные методы:**
- `get_sample(sample_id)` - получить образец по ID
- `get_sample_by_name(name)` - получить образец по имени
- `get_samples(subset_id)` - получить образцы группы
- `add_sample(name, subset_id, additions)` - создать образец

---

## Примеры использования

### Пример 1: Безопасное удаление группы

```python
async def safe_delete_group(project: Project, group_id: int):
    """Удалить группу, предварительно переместив образцы."""
    # Получить образцы группы
    samples = await project.get_samples(subset_id=group_id)
    
    if samples:
        print(f"Found {len(samples)} samples in group")
        
        # Переместить образцы в другую группу или убрать группу
        for sample in samples:
            sample.subset_id = None  # Или ID другой группы
            await project.update_sample(sample)
        
        print("Samples moved")
    
    # Теперь можно удалить группу
    await project.delete_subset(group_id)
    print("Group deleted")
```

### Пример 2: Массовое изменение группы

```python
async def bulk_change_group(
    project: Project,
    sample_names: list[str],
    new_group_id: int
):
    """Изменить группу для нескольких образцов."""
    for name in sample_names:
        sample = await project.get_sample_by_name(name)
        if sample:
            sample.subset_id = new_group_id
            await project.update_sample(sample)
            print(f"Updated {name}")
```

### Пример 3: Удаление инструмента с очисткой идентификаций

```python
async def delete_tool_with_cleanup(project: Project, tool_id: int):
    """
    Удалить инструмент вместе с его идентификациями.
    
    ВНИМАНИЕ: Это удалит все идентификации!
    """
    # Получить все идентификации инструмента
    identifications = await project.get_identifications(tool_id=tool_id)
    
    if len(identifications) > 0:
        print(f"WARNING: This will delete {len(identifications)} identifications!")
        confirm = input("Type 'yes' to confirm: ")
        
        if confirm.lower() != 'yes':
            print("Cancelled")
            return
        
        # Удалить идентификации вручную (через SQL API)
        await project.execute_query(
            "DELETE FROM identification WHERE tool_id = ?",
            (tool_id,)
        )
        print(f"Deleted {len(identifications)} identifications")
    
    # Теперь можно удалить инструмент
    await project.delete_tool(tool_id)
    print("Tool deleted")
```

### Пример 4: Проверка перед удалением

```python
async def can_delete_group(project: Project, group_id: int) -> bool:
    """Проверить, можно ли удалить группу."""
    samples = await project.get_samples(subset_id=group_id)
    return len(samples) == 0

async def can_delete_tool(project: Project, tool_id: int) -> bool:
    """Проверить, можно ли удалить инструмент."""
    identifications = await project.get_identifications(tool_id=tool_id)
    return len(identifications) == 0

# Использование
async def safe_operations():
    async with Project("myproject.dasmix") as project:
        if await can_delete_group(project, 5):
            await project.delete_subset(5)
            print("Group deleted")
        else:
            print("Cannot delete group - has samples")
```

---

## Диаграмма зависимостей

```
Subset (Group)
    ↓
Sample
    ↓
Spectre_File
    ↓
Spectre → Identification
              ↑
            Tool
```

**Правила удаления:**
- `Subset` можно удалить только если нет связанных `Sample`
- `Tool` можно удалить только если нет связанных `Identification`
- `Sample` можно изменить (в т.ч. `subset_id`) в любое время

---

## Рекомендации

### Удаление групп

1. **Всегда проверяйте наличие образцов** перед удалением группы
2. **Используйте try-except** для обработки ошибок удаления
3. **Уведомляйте пользователя** о невозможности удаления
4. **Предлагайте альтернативы**: переместить образцы в другую группу

### Удаление инструментов

1. **Будьте осторожны**: идентификации - ценные данные
2. **Предупреждайте пользователя** о последствиях
3. **Рассмотрите архивирование** вместо удаления
4. **Логируйте операции удаления** для возможности восстановления

### Изменение групп образцов

1. **Обновляйте UI** после изменения группы
2. **Пересчитывайте счетчики** образцов в группах
3. **Валидируйте subset_id** перед сохранением
4. **Используйте транзакции** для массовых операций

---

## Связанные документы

- [MASTER_SPEC.md](../MASTER_SPEC.md) - основная спецификация
- [PROJECT_ER.mermaid](../PROJECT_ER.mermaid) - схема базы данных
- [SESSION_2026_01_30_DELETION_AND_GROUP_CHANGE.md](../changes/SESSION_2026_01_30_DELETION_AND_GROUP_CHANGE.md) - описание изменений
