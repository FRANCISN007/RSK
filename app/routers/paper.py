
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.models.user import User
from app.models.membership import Membership
from app.models.paper_category import PaperCategory
from app.models.paper import Paper
from app.models.paper_week import PaperWeek

from app.models.paper_page import PaperPage

from app.models.week_paper import EditionPaper



from app.models.edition_paper_page import EditionPaperPage

from app.schemas.paper import (
    PaperCategoryCreate,
    PaperCategoryUpdate,
    PaperCategoryResponse,
    PaperCreate,
    PaperUpdate,
    PaperResponse,
    PaperWeekCreate,
    PaperWeekUpdate,
    PaperWeekResponse,
    PaperPageResponse,
    PublicPaperResponse,
    PublicPaperPageResponse,
    PaperPageCreate,
)


router = APIRouter(
    prefix="/papers",
    tags=["Papers"],
)


# ============================================================
# FILE STORAGE
# ============================================================

BASE_UPLOAD_DIR = Path("uploads/papers")

ALLOWED_FILE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}


def save_uploaded_file(
    upload_file: UploadFile,
    category_slug: str,
    paper_slug: str,
    page_number: int,
) -> tuple[str, str]:

    if upload_file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG, and PDF files are allowed.",
        )

    extension = ALLOWED_FILE_TYPES[upload_file.content_type]

    directory = (
        BASE_UPLOAD_DIR
        / category_slug
        / paper_slug
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        f"page-{page_number}-{uuid4().hex}{extension}"
    )

    file_path = directory / filename

    with file_path.open("wb") as buffer:
        while chunk := upload_file.file.read(1024 * 1024):
            buffer.write(chunk)

    return (
        str(file_path).replace("\\", "/"),
        upload_file.content_type,
    )



def save_edition_page(
    db: Session,
    week_paper: EditionPaper,
    page_number: int,
    file: UploadFile,
    marked: bool,
):
    if page_number < 1 or page_number > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be between 1 and 4.",
        )

    paper = db.get(Paper, week_paper.paper_id)

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    category = db.get(PaperCategory, paper.category_id)

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper category not found.",
        )

    file_path, file_type = save_uploaded_file(
        upload_file=file,
        category_slug=category.slug,
        paper_slug=paper.slug,
        page_number=page_number,
    )

    page = db.execute(
        select(EditionPaperPage).where(
            EditionPaperPage.edition_paper_id == week_paper.id,
            EditionPaperPage.page_number == page_number,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if page is None:
        page = EditionPaperPage(
            edition_paper_id=week_paper.id,
            page_number=page_number,
        )
        db.add(page)

    page.file_path = file_path
    page.file_type = file_type
    page.is_marked = marked
    page.uploaded_at = now
    page.marked_at = now if marked else None

    try:
        db.commit()
        db.refresh(page)
    except Exception:
        db.rollback()
        raise

    return {
        "message": (
            "Marked page uploaded successfully."
            if marked
            else "Unmarked page uploaded successfully."
        ),
        "edition_paper_id": week_paper.id,
        "page_id": page.id,
        "page_number": page.page_number,
        "file_path": page.file_path,
        "file_type": page.file_type,
        "is_marked": page.is_marked,
        "uploaded_at": page.uploaded_at,
        "marked_at": page.marked_at,
    }







# ============================================================
# CATEGORY MANAGEMENT
# ============================================================

@router.post(
    "/categories",
    response_model=PaperCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    data: PaperCategoryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing_name = db.scalar(
        select(PaperCategory).where(
            PaperCategory.name == data.name
        )
    )

    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paper category already exists.",
        )

    existing_slug = db.scalar(
        select(PaperCategory).where(
            PaperCategory.slug == data.slug
        )
    )

    if existing_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paper category slug already exists.",
        )

    category = PaperCategory(
        name=data.name,
        slug=data.slug,
        description=data.description,
        is_active=data.is_active,
        display_order=data.display_order,
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.get(
    "/categories",
    response_model=list[PaperCategoryResponse],
)
def list_categories(
    db: Session = Depends(get_db),
):
    categories = db.scalars(
        select(PaperCategory)
        .order_by(
            PaperCategory.display_order,
            PaperCategory.name,
        )
    ).all()

    return categories


@router.put(
    "/categories/{category_id}",
    response_model=PaperCategoryResponse,
)
def update_category(
    category_id: int,
    data: PaperCategoryUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    category = db.get(
        PaperCategory,
        category_id,
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper category not found.",
        )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if data.name is not None:
        existing = db.scalar(
            select(PaperCategory).where(
                PaperCategory.name == data.name,
                PaperCategory.id != category_id,
            )
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Paper category name already exists.",
            )

        category.name = data.name

    # --------------------------------------------------------
    # SLUG
    # --------------------------------------------------------

    if data.slug is not None:
        existing = db.scalar(
            select(PaperCategory).where(
                PaperCategory.slug == data.slug,
                PaperCategory.id != category_id,
            )
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Paper category slug already exists.",
            )

        category.slug = data.slug

    # --------------------------------------------------------
    # OTHER FIELDS
    # --------------------------------------------------------

    if data.description is not None:
        category.description = data.description

    if data.is_active is not None:
        category.is_active = data.is_active

    if data.display_order is not None:
        category.display_order = data.display_order

    db.commit()
    db.refresh(category)

    return category


# ============================================================
# PAPER MANAGEMENT
# ============================================================

@router.post(
    "",
    response_model=PaperResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_paper(
    data: PaperCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    category = db.get(
        PaperCategory,
        data.category_id,
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper category not found.",
        )

    existing = db.scalar(
        select(Paper).where(
            Paper.slug == data.slug
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paper slug already exists.",
        )

    paper = Paper(
        category_id=data.category_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        is_active=data.is_active,
        display_order=data.display_order,
    )

    db.add(paper)
    db.commit()
    db.refresh(paper)

    return paper


@router.get(
    "",
    response_model=list[PaperResponse],
)
def list_papers(
    category_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = select(Paper)

    if category_id is not None:
        query = query.where(
            Paper.category_id == category_id
        )

    query = query.order_by(
        Paper.display_order,
        Paper.name,
    )

    return db.scalars(query).all()


@router.get(
    "/{paper_id}",
    response_model=PaperResponse,
)
def get_paper(
    paper_id: int,
    db: Session = Depends(get_db),
):
    paper = db.get(
        Paper,
        paper_id,
    )

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    return paper


@router.put(
    "/{paper_id}",
    response_model=PaperResponse,
)
def update_paper(
    paper_id: int,
    data: PaperUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    paper = db.get(
        Paper,
        paper_id,
    )

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    if data.category_id is not None:
        category = db.get(
            PaperCategory,
            data.category_id,
        )

        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper category not found.",
            )

        paper.category_id = data.category_id

    if data.slug is not None:
        existing = db.scalar(
            select(Paper).where(
                Paper.slug == data.slug,
                Paper.id != paper_id,
            )
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Paper slug already exists.",
            )

        paper.slug = data.slug

    if data.name is not None:
        paper.name = data.name

    if data.description is not None:
        paper.description = data.description

    if data.is_active is not None:
        paper.is_active = data.is_active

    if data.display_order is not None:
        paper.display_order = data.display_order

    db.commit()
    db.refresh(paper)

    return paper



@router.delete(
    "/{category_id}/{paper_id}",
    status_code=status.HTTP_200_OK,
)
def delete_paper(
    category_id: int,
    paper_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    category = db.get(
        PaperCategory,
        category_id,
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper category not found.",
        )

    paper = db.scalar(
        select(Paper).where(
            Paper.id == paper_id,
            Paper.category_id == category_id,
        )
    )

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found in this category.",
        )

    # --------------------------------------------------------
    # CHECK WHETHER THIS PAPER HAS BEEN ADDED TO ANY WEEK
    # --------------------------------------------------------
    existing_week_paper = db.scalar(
        select(EditionPaper).where(
            EditionPaper.paper_id == paper_id
        )
    )

    if existing_week_paper is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This paper cannot be deleted because it has already "
                "been added to a week."
            ),
        )

    paper_name = paper.name

    db.delete(paper)
    db.commit()

    return {
        "message": (
            f"Paper '{paper_name}' deleted successfully."
        )
    }



# ============================================================
# WEEK MANAGEMENT
# ============================================================

@router.post(
    "/categories/{category_id}/weeks",
    response_model=PaperWeekResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_week(
    category_id: int,
    data: PaperWeekCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    category = db.get(
        PaperCategory,
        category_id,
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper category not found.",
        )

    existing = db.scalar(
        select(PaperWeek).where(
            PaperWeek.category_id == category_id,
            PaperWeek.year == data.year,
            PaperWeek.week_number == data.week_number,
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This category already has a week "
                "for this year and week number."
            ),
        )

    week = PaperWeek(
        category_id=category_id,
        year=data.year,
        week_number=data.week_number,
        status="draft",
    )

    db.add(week)
    db.commit()
    db.refresh(week)

    return week


@router.get(
    "/categories/{category_id}/weeks",
    response_model=list[PaperWeekResponse],
)
def list_category_weeks(
    category_id: int,
    db: Session = Depends(get_db),
):
    category = db.get(
        PaperCategory,
        category_id,
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper category not found.",
        )

    weeks = db.scalars(
        select(PaperWeek)
        .where(
            PaperWeek.category_id == category_id
        )
        .order_by(
            PaperWeek.year.desc(),
            PaperWeek.week_number.desc(),
        )
    ).all()

    return weeks


@router.get(
    "/categories/{category_id}/weeks/{week_id}",
    response_model=PaperWeekResponse,
)
def get_week(
    category_id: int,
    week_id: int,
    db: Session = Depends(get_db),
):
    week = db.scalar(
        select(PaperWeek).where(
            PaperWeek.id == week_id,
            PaperWeek.category_id == category_id,
        )
    )

    if week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper week not found in this category.",
        )

    return week


@router.put(
    "/categories/{category_id}/weeks/{week_id}",
    response_model=PaperWeekResponse,
)
def update_week(
    category_id: int,
    week_id: int,
    data: PaperWeekUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    week = db.scalar(
        select(PaperWeek).where(
            PaperWeek.id == week_id,
            PaperWeek.category_id == category_id,
        )
    )

    if week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper week not found in this category.",
        )

    if data.status is not None:
        allowed_statuses = {
            "draft",
            "published",
            "result_available",
            "archived",
        }

        if data.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid paper week status.",
            )

        week.status = data.status

        if data.status == "published":
            week.published_at = datetime.now(
                timezone.utc
            )

    db.commit()
    db.refresh(week)

    return week



@router.post(
    "/weeks/{week_id}/publish",
)
def publish_week(
    week_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    week = db.scalar(
        select(PaperWeek).where(
            PaperWeek.id == week_id
        )
    )

    if week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Week not found.",
        )

    # A week must contain at least one paper before it can be published.
    paper_count = db.scalar(
        select(func.count(EditionPaper.id)).where(
            EditionPaper.edition_id == week_id
        )
    )

    if paper_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish a week without papers.",
        )

    if week.status == "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Week is already published.",
        )

    week.status = "published"
    week.published_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(week)

    return {
        "message": "Week published successfully.",
        "week_id": week.id,
        "category_id": week.category_id,
        "year": week.year,
        "week_number": week.week_number,
        "status": week.status,
        "published_at": week.published_at,
    }




# ============================================================
# ADD PAPER TO WEEK
# ============================================================

@router.post(
    "/weeks/{week_id}/papers/{paper_id}",
    status_code=status.HTTP_201_CREATED,
)
def add_paper_to_week(
    week_id: int,
    paper_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    week = db.get(
        PaperWeek,
        week_id,
    )

    if week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper week not found.",
        )

    paper = db.get(
        Paper,
        paper_id,
    )

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    if paper.category_id != week.category_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This paper does not belong to "
                "the week's category."
            ),
        )

    # --------------------------------------------------------
    # CHECK WHETHER THIS PAPER IS ALREADY IN THIS WEEK
    # --------------------------------------------------------

    existing = db.scalar(
        select(EditionPaper).where(
            EditionPaper.edition_id == week_id,
            EditionPaper.paper_id == paper_id,
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This paper is already part of this week.",
        )

    # --------------------------------------------------------
    # GET NEXT DISPLAY ORDER
    # --------------------------------------------------------

    max_order = db.scalar(
        select(EditionPaper.display_order)
        .where(
            EditionPaper.edition_id == week_id
        )
        .order_by(
            EditionPaper.display_order.desc()
        )
        .limit(1)
    )

    display_order = (
        max_order + 1
        if max_order is not None
        else 1
    )

    # --------------------------------------------------------
    # CREATE WEEK-PAPER ASSOCIATION
    # --------------------------------------------------------

    week_paper = EditionPaper(
        edition_id=week_id,
        paper_id=paper_id,
        display_order=display_order,
    )

    db.add(week_paper)
    db.commit()
    db.refresh(week_paper)

    return {
        "id": week_paper.id,
        "week_id": week_paper.edition_id,
        "paper_id": week_paper.paper_id,
        "display_order": week_paper.display_order,
    }



# ============================================================
# REMOVE PAPER FROM WEEK
# ============================================================

@router.delete(
    "/weeks/{week_id}/papers/{paper_id}",
)
def remove_paper_from_week(
    week_id: int,
    paper_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    week_paper = db.scalar(
        select(EditionPaper).where(
            EditionPaper.edition_id == week_id,
            EditionPaper.paper_id == paper_id,
        )
    )

    if week_paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper is not part of this week.",
        )

    db.delete(week_paper)
    db.commit()

    return {
        "message": "Paper removed from week."
    }


# ============================================================
# LIST PAPERS AND PAGES IN WEEK
# ============================================================

@router.get("/weeks/{week_id}/papers")
def list_week_papers(
    week_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Enforce current-week / historical-week access.
    get_accessible_week(
        db=db,
        week_id=week_id,
        user=current_user,
    )

    week = db.scalars(
        select(PaperWeek)
        .options(
            joinedload(PaperWeek.week_papers).joinedload(
                EditionPaper.paper
            ),
            joinedload(PaperWeek.week_papers).joinedload(
                EditionPaper.pages
            ),
        )
        .where(PaperWeek.id == week_id)
    ).unique().first()

    if week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper week not found.",
        )

    papers = []

    for week_paper in sorted(
        week.week_papers,
        key=lambda item: item.display_order,
    ):
        paper = week_paper.paper

        if paper is None or not paper.is_active:
            continue

        pages = sorted(
            week_paper.pages,
            key=lambda page: page.page_number,
        )

        papers.append(
            {
                "id": paper.id,
                "week_paper_id": week_paper.id,
                "paper_id": paper.id,
                "name": paper.name,
                "slug": paper.slug,
                "description": paper.description,
                "display_order": week_paper.display_order,
                "pages": [
                    {
                        "id": page.id,
                        "page_number": page.page_number,
                        "file_path": page.file_path,
                        "file_type": page.file_type,
                        "is_marked": page.is_marked,
                        "uploaded_at": page.uploaded_at,
                        "marked_at": page.marked_at,
                    }
                    for page in pages
                ],
            }
        )

    return {
        "week_id": week.id,
        "category_id": week.category_id,
        "year": week.year,
        "week_number": week.week_number,
        "status": week.status,
        "papers": papers,
    }


# ============================================================
# LIST PAGES FOR A PAPER IN A WEEK
# ============================================================

@router.get("/weeks/{week_id}/papers/{week_paper_id}/pages")
def list_week_paper_pages(
    week_id: int,
    week_paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Enforce current-week / historical-week access.
    get_accessible_week(
        db=db,
        week_id=week_id,
        user=current_user,
    )

    week_paper = db.scalar(
        select(EditionPaper).where(
            EditionPaper.id == week_paper_id,
            EditionPaper.edition_id == week_id,
        )
    )

    if week_paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper is not part of this week.",
        )

    pages = db.scalars(
        select(EditionPaperPage)
        .where(
            EditionPaperPage.edition_paper_id == week_paper.id
        )
        .order_by(EditionPaperPage.page_number)
    ).all()

    return [
        {
            "id": page.id,
            "edition_paper_id": page.edition_paper_id,
            "page_number": page.page_number,
            "file_path": page.file_path,
            "file_type": page.file_type,
            "is_marked": page.is_marked,
            "uploaded_at": page.uploaded_at,
            "marked_at": page.marked_at,
        }
        for page in pages
    ]


# ============================================================
# CREATE PAGE NUMBER
# ============================================================


@router.post(
    "/papers/{paper_id}/pages",
    response_model=PaperPageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_page(
    paper_id: int,
    data: PaperPageCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # --------------------------------------------------------
    # Validate page number.
    # --------------------------------------------------------

    if data.page_number < 1 or data.page_number > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be between 1 and 4.",
        )

    # --------------------------------------------------------
    # Make sure the Paper exists.
    # Pages belong directly to the permanent Paper.
    # Week is NOT involved at this stage.
    # --------------------------------------------------------

    paper = db.get(Paper, paper_id)

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    # --------------------------------------------------------
    # Make sure the page does not already exist.
    # --------------------------------------------------------

    existing_page = db.scalar(
        select(PaperPage).where(
            PaperPage.paper_id == paper_id,
            PaperPage.page_number == data.page_number,
        )
    )

    if existing_page is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Page {data.page_number} already exists "
                "for this paper."
            ),
        )

    # --------------------------------------------------------
    # Create the page record first.
    # The file is uploaded later.
    # --------------------------------------------------------

    page = PaperPage(
        paper_id=paper_id,
        page_number=data.page_number,
        file_path=None,
        file_type=None,
        is_marked=False,
        marked_at=None,
    )

    db.add(page)
    db.commit()
    db.refresh(page)

    return {
        "id": page.id,
        "paper_id": page.paper_id,
        "page_number": page.page_number,
        "file_path": page.file_path,
        "file_type": page.file_type,
        "is_marked": page.is_marked,
        "uploaded_at": page.uploaded_at,
        "marked_at": page.marked_at,
    }



@router.get(
    "/papers/{paper_id}/pages",
    response_model=list[PaperPageResponse],
)
def list_pages(
    paper_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    paper = db.get(Paper, paper_id)

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    pages = db.scalars(
        select(PaperPage)
        .where(
            PaperPage.paper_id == paper_id,
        )
        .order_by(
            PaperPage.page_number,
        )
    ).all()

    return [
        {
            "id": page.id,
            "paper_id": page.paper_id,
            "page_number": page.page_number,
            "file_path": page.file_path,
            "file_type": page.file_type,
            "is_marked": page.is_marked,
            "uploaded_at": page.uploaded_at,
            "marked_at": page.marked_at,
        }
        for page in pages
    ]

@router.put(
    "/papers/{paper_id}/pages/{page_id}",
    response_model=PaperPageResponse,
)
def update_page(
    paper_id: int,
    page_id: int,
    data: PaperPageCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if data.page_number < 1 or data.page_number > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be between 1 and 4.",
        )

    paper = db.get(Paper, paper_id)

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    page = db.scalar(
        select(PaperPage).where(
            PaperPage.id == page_id,
            PaperPage.paper_id == paper_id,
        )
    )

    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found.",
        )

    existing_page = db.scalar(
        select(PaperPage).where(
            PaperPage.paper_id == paper_id,
            PaperPage.page_number == data.page_number,
            PaperPage.id != page_id,
        )
    )

    if existing_page is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Page {data.page_number} already exists "
                "for this paper."
            ),
        )

    page.page_number = data.page_number

    db.commit()
    db.refresh(page)

    return {
        "id": page.id,
        "paper_id": page.paper_id,
        "page_number": page.page_number,
        "file_path": page.file_path,
        "file_type": page.file_type,
        "is_marked": page.is_marked,
        "uploaded_at": page.uploaded_at,
        "marked_at": page.marked_at,
    }



@router.delete(
    "/papers/{paper_id}/pages/{page_id}",
)
def delete_page(
    paper_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    paper = db.get(Paper, paper_id)

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    page = db.scalar(
        select(PaperPage).where(
            PaperPage.id == page_id,
            PaperPage.paper_id == paper_id,
        )
    )

    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found.",
        )

    db.delete(page)
    db.commit()

    return {
        "message": "Page deleted successfully.",
        "page_id": page_id,
        "paper_id": paper_id,
    }




# ============================================================
# UPLOAD / REPLACE UNMARKED PAGE
# ============================================================



@router.post("/week-papers/{week_paper_id}/pages/{page_number}")
def upload_edition_page(
    week_paper_id: int,
    page_number: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    week_paper = db.get(EditionPaper, week_paper_id)

    if week_paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper is not assigned to a week.",
        )

    return save_edition_page(
        db=db,
        week_paper=week_paper,
        page_number=page_number,
        file=file,
        marked=False,
    )


@router.post(
    "/week-papers/{week_paper_id}/pages/{page_number}/marked"
)
def upload_marked_edition_page(
    week_paper_id: int,
    page_number: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    week_paper = db.get(EditionPaper, week_paper_id)

    if week_paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper is not assigned to a week.",
        )

    return save_edition_page(
        db=db,
        week_paper=week_paper,
        page_number=page_number,
        file=file,
        marked=True,
    )


# ============================================================
# PUBLIC CURRENT WEEK
# ============================================================



@router.get(
    "/public/current",
)
def get_current_public_papers(
    category_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = (
        select(PaperWeek)
        .options(
            joinedload(
                PaperWeek.category
            ),
            joinedload(
                PaperWeek.week_papers
            )
            .joinedload(
                EditionPaper.pages
            ),
        )
        .where(
            PaperWeek.status.in_(
                [
                    "published",
                    "result_available",
                ]
            )
        )
    )

    if category_id is not None:
        query = query.where(
            PaperWeek.category_id == category_id
        )

    week = db.scalars(
        query.order_by(
            PaperWeek.year.desc(),
            PaperWeek.week_number.desc(),
        )
    ).first()

    if week is None:
        return None

    papers = []

    for week_paper in sorted(
        week.week_papers,
        key=lambda x: x.display_order,
    ):
        paper = week_paper.paper

        if paper is None:
            continue

        if not paper.is_active:
            continue

        pages = sorted(
            week_paper.pages,
            key=lambda x: x.page_number,
        )

        papers.append(
            {
                "id": paper.id,
                "category_id": paper.category_id,
                "name": paper.name,
                "slug": paper.slug,
                "description": paper.description,
                "week_id": week.id,
                "week_paper_id": week_paper.id,
                "year": week.year,
                "week_number": week.week_number,
                "status": week.status,
                "pages": [
                    {
                        "id": page.id,
                        "page_number": page.page_number,
                        "file_path": page.file_path,
                        "file_type": page.file_type,
                        "is_marked": page.is_marked,
                    }
                    for page in pages
                ],
            }
        )

    return {
        "week_id": week.id,
        "category_id": week.category_id,
        "year": week.year,
        "week_number": week.week_number,
        "status": week.status,
        "papers": papers,
    }



def has_active_membership(
    db: Session,
    user_id: int,
) -> bool:

    now = datetime.now(timezone.utc)

    membership = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.status == "active",
            Membership.start_date <= now,
            Membership.end_date >= now,
        )
        .order_by(
            Membership.end_date.desc()
        )
    )

    return membership is not None


def get_accessible_week(
    db: Session,
    week_id: int,
    user: User,
) -> PaperWeek:
    week = db.scalar(
        select(PaperWeek).where(
            PaperWeek.id == week_id,
            PaperWeek.status.in_(
                ["published", "result_available"]
            ),
        )
    )

    if week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published paper week not found.",
        )

    current_week = db.scalar(
        select(PaperWeek)
        .where(
            PaperWeek.category_id == week.category_id,
            PaperWeek.status.in_(
                ["published", "result_available"]
            ),
        )
        .order_by(
            PaperWeek.year.desc(),
            PaperWeek.week_number.desc(),
        )
        .limit(1)
    )

    if current_week is not None and week.id != current_week.id:
        if not has_active_membership(db, user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "An active membership is required "
                    "to view paper history."
                ),
            )

    return week


# ============================================================
# HISTORICAL WEEK
# ============================================================



@router.get("/weeks/{week_id}/public")
def get_week_for_user(
    week_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Shared access control.
    week = get_accessible_week(
        db=db,
        week_id=week_id,
        user=current_user,
    )

    # Load both paper metadata and the pages belonging to this week.
    week = db.scalars(
        select(PaperWeek)
        .options(
            joinedload(PaperWeek.week_papers).joinedload(
                EditionPaper.paper
            ),
            joinedload(PaperWeek.week_papers).joinedload(
                EditionPaper.pages
            ),
        )
        .where(PaperWeek.id == week.id)
    ).unique().first()

    papers = []

    for week_paper in sorted(
        week.week_papers,
        key=lambda item: item.display_order,
    ):
        paper = week_paper.paper

        if paper is None or not paper.is_active:
            continue

        pages = sorted(
            week_paper.pages,
            key=lambda page: page.page_number,
        )

        papers.append(
            {
                "id": paper.id,
                "category_id": paper.category_id,
                "name": paper.name,
                "slug": paper.slug,
                "description": paper.description,
                "week_id": week.id,
                "week_paper_id": week_paper.id,
                "year": week.year,
                "week_number": week.week_number,
                "status": week.status,
                "pages": [
                    {
                        "id": page.id,
                        "page_number": page.page_number,
                        "file_path": page.file_path,
                        "file_type": page.file_type,
                        "is_marked": page.is_marked,
                    }
                    for page in pages
                ],
            }
        )

    return {
        "week_id": week.id,
        "category_id": week.category_id,
        "year": week.year,
        "week_number": week.week_number,
        "status": week.status,
        "papers": papers,
    }

