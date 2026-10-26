package com.team.shop.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "product_image")
public class ProductImage {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    @Column(name = "image_path", nullable = false, length = 500)
    private String imagePath;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    protected ProductImage() {
    }

    public ProductImage(Product product, String imagePath, int sortOrder) {
        this.product = product;
        this.imagePath = imagePath;
        this.sortOrder = sortOrder;
    }

    public Long getId() { return id; }
    public String getImagePath() { return imagePath; }
    public int getSortOrder() { return sortOrder; }
}
